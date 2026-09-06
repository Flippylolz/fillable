import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from test_storage_maintenance import storage as storage
from test_storage_service import counters, save
from test_storage_service import setup as setup

from app.accounts.service import reset_password
from app.errors import AppError
from app.infrastructure import database
from app.main import app
from app.storage import quota_cli, quotas
from app.storage.schema import MAX_BYTES, audit_events, settings
from app.storage.service import StorageError


def test_default_override_zero_inherit_and_audit(storage):
    _, owner, other, _ = storage
    assert quotas.set_default(100) == {"default_limit_bytes": 100, "revision": 1}
    assert quotas.set_default(100)["revision"] == 1
    assert quotas.usage(owner).limit_bytes == quotas.usage(other).limit_bytes == 100
    assert quotas.set_override(owner, 200).limit_bytes == 200
    quotas.set_override(owner, 200)
    quotas.set_default(50)
    assert (
        quotas.usage(owner).limit_bytes == 200 and quotas.usage(other).limit_bytes == 50
    )
    assert quotas.set_override(owner, 0).available_bytes == 0
    assert quotas.set_override(owner, None).limit_bytes == 50
    assert quotas.set_override(owner, MAX_BYTES).limit_bytes == MAX_BYTES
    with database().connect() as connection:
        rows = (
            connection.execute(select(audit_events).order_by(audit_events.c.created_at))
            .mappings()
            .all()
        )
    assert len(rows) == 6
    assert rows[0]["details"] == {"before": 1024**3, "after": 100, "revision": 1}
    assert rows[1]["details"] == {"before": None, "after": 200}
    assert rows[4]["details"] == {"before": 0, "after": None}
    assert all(row["actor_id"] is None for row in rows)
    for invalid in (-1, True, 1.5, "1", MAX_BYTES + 1):
        for change in (
            quotas.set_default,
            lambda value: quotas.set_override(owner, value),
        ):
            with pytest.raises(ValueError):
                change(invalid)
    with pytest.raises(AppError):
        quotas.usage(uuid4())
    with pytest.raises(StorageError, match="not_found"):
        quotas.set_override(uuid4(), 1)


def test_lowering_preserves_files_and_aborts_inflight_allocations(storage):
    store, owner, _, _ = storage
    original = save(store, owner)
    quotas.set_default(20)

    def lowered():
        yield b"12"
        quotas.set_default(0)

    with pytest.raises(StorageError, match="quota_exceeded"):
        store.store(
            owner, "lower-default", "a" * 64, "version", lowered(), expected_bytes=2
        )
    assert counters(owner) == (8, 0)
    usage = quotas.usage(owner)
    assert usage.used_bytes == 8 and usage.over_limit and usage.available_bytes == 0
    with store.read(owner, original.id) as stream:
        assert stream.read() == b"original"
    with pytest.raises(StorageError, match="quota_exceeded"):
        save(store, owner)
    quotas.set_override(owner, 20)

    def overridden():
        yield b"12"
        quotas.set_override(owner, 0)

    with pytest.raises(StorageError, match="quota_exceeded"):
        store.store(owner, "lower-override", "a" * 64, "version", overridden())
    assert counters(owner) == (8, 0)


def test_operator_change_serializes_with_reservation_settings_lock(storage):
    _, owner, _, _ = storage
    started = Event()

    def change():
        started.set()
        return quotas.set_override(owner, 0)

    with ThreadPoolExecutor(1) as pool:
        with database().begin() as connection:
            connection.execute(select(settings).with_for_update())
            future = pool.submit(change)
            assert started.wait(5)
            deadline = time.monotonic() + 5
            while True:
                with database().connect() as observer:
                    waiting = observer.execute(
                        text("""
                        SELECT count(*) FROM pg_stat_activity
                        WHERE datname = current_database() AND wait_event_type = 'Lock'
                          AND query LIKE '%storage_settings%'
                    """)
                    ).scalar_one()
                if waiting:
                    break
                assert not future.done() and time.monotonic() < deadline
                Event().wait(0.01)
            assert not future.done()
            assert quotas.usage(owner).limit_bytes == 1024**3
        assert future.result(5).limit_bytes == 0


def client_for(owner):
    password = "Synthetic-quota-їжак-2026"
    email = f"{owner}@example.test"
    reset_password(email, password)
    client = TestClient(app)
    csrf = client.get("/api/auth/session").json()["csrf_token"]
    assert (
        client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        ).status_code
        == 200
    )
    return client


def test_usage_api_is_authenticated_owner_scoped_exact_and_read_only(storage):
    store, owner, other, _ = storage
    save(store, owner)
    quotas.set_override(owner, 10)
    quotas.set_override(other, 0)
    assert TestClient(app).get("/api/storage/usage").status_code == 401
    first, second = client_for(owner), client_for(other)
    result = first.get(f"/api/storage/usage?owner_id={other}")
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert result.json() == {
        "limit_bytes": 10,
        "used_bytes": 8,
        "reserved_bytes": 0,
        "available_bytes": 2,
        "over_limit": False,
    }
    assert second.get("/api/storage/usage").json()["limit_bytes"] == 0
    assert (
        first.post("/api/storage/usage", json={"limit_bytes": 999}).status_code == 405
    )
    assert (
        first.patch("/api/storage/usage", json={"owner_id": str(other)}).status_code
        == 405
    )
    quotas.set_override(owner, 0)
    assert first.get("/api/storage/usage").json()["over_limit"]
    assert counters(owner) == (8, 0)


def test_private_operator_commands_and_errors(storage, capsys):
    _, owner, _, _ = storage
    email = f"{owner}@example.test"
    assert quota_cli.main(["default", "--bytes", "100"]) == 0
    assert json.loads(capsys.readouterr().out)["default_limit_bytes"] == 100
    assert quota_cli.main(["override", "--email", email.upper(), "--bytes", "0"]) == 0
    assert json.loads(capsys.readouterr().out)["limit_bytes"] == 0
    assert quota_cli.main(["inherit", "--email", email]) == 0
    assert json.loads(capsys.readouterr().out)["limit_bytes"] == 100
    assert quota_cli.main(["show", "--email", f" {email} "]) == 0
    assert json.loads(capsys.readouterr().out)["available_bytes"] == 100
    for args in (
        ["default", "--bytes", "-1"],
        ["show", "--email", "absent@example.test"],
    ):
        assert quota_cli.main(args) == 1
        assert json.loads(capsys.readouterr().out) == {"error": "quota_command_failed"}
    with pytest.raises(SystemExit):
        quota_cli.main(["inherit", "--email", email, "--bytes", "1"])
    capsys.readouterr()
    result = subprocess.run(
        [sys.executable, "-m", "app.storage.quota_cli", "show", "--email", email],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and json.loads(result.stdout)["limit_bytes"] == 100
    assert email not in result.stdout
