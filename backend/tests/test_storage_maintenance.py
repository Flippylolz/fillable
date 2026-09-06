import json
import subprocess
import sys
from contextlib import contextmanager
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select, update
from test_storage_service import counters, expire, operation, save
from test_storage_service import setup as setup

from app.infrastructure import database
from app.storage import configuration, maintenance
from app.storage.schema import accounts, audit_events, files
from app.storage.service import StorageError


@pytest.fixture
def storage(setup):
    yield setup
    with database().begin() as connection:
        connection.execute(delete(audit_events))


def test_delete_is_owner_checked_durable_and_idempotent(storage):
    store, owner, other, root = storage
    original, copy = save(store, owner), save(store, owner)
    with pytest.raises(StorageError, match="not_found"):
        maintenance.delete_file(store, other, copy.id)
    with store.read(owner, original.id) as stream:
        assert maintenance.delete_file(store, owner, copy.id)
        assert stream.read() == b"original"
    assert not maintenance.delete_file(store, owner, copy.id)
    assert counters(owner) == (8, 0)
    assert not (root / "files" / str(owner) / str(copy.id)).exists()
    with database().connect() as connection:
        actions = connection.execute(select(audit_events.c.action)).scalars().all()
    assert sorted(actions) == ["deletion_completed", "deletion_requested"]
    with pytest.raises(RuntimeError, match="Storage audit exists"):
        command.downgrade(Config("alembic.ini"), "0003_storage_models")
    with pytest.raises(StorageError, match="not_found"):
        with store.read(owner, copy.id):
            pass


def test_live_readers_protect_bytes_and_ready_is_rechecked(storage, monkeypatch):
    store, owner, _, _ = storage
    result = save(store, owner)
    with store.read(owner, result.id) as first, store.read(owner, result.id) as second:
        with pytest.raises(StorageError, match="operation_in_progress"):
            maintenance.delete_file(store, owner, result.id)
        assert first.read() == second.read() == b"original"
    op = operation(owner)
    with store.fs.lock(op["id"]):
        with pytest.raises(StorageError, match="operation_in_progress"):
            with store.read(owner, result.id):
                pass
    lock = store.fs.lock

    @contextmanager
    def raced(*args, **kwargs):
        maintenance.delete_file(store, owner, result.id)
        with lock(*args, **kwargs):
            yield

    # Use original lock for deletion, then simulate deletion before the reader lock.
    @contextmanager
    def reader_raced(*args, **kwargs):
        if kwargs.get("shared"):
            with raced(*args, **kwargs):
                yield
        else:
            with lock(*args, **kwargs):
                yield

    monkeypatch.setattr(store.fs, "lock", reader_raced)
    with pytest.raises(StorageError, match="not_found"):
        with store.read(owner, result.id):
            pass


def test_failed_physical_deletion_stays_charged_and_reconcile_finishes(
    storage, monkeypatch
):
    store, owner, _, root = storage
    result = save(store, owner)
    remove = store.fs.remove
    monkeypatch.setattr(
        store.fs, "remove", lambda *args: (_ for _ in ()).throw(OSError())
    )
    with pytest.raises(StorageError, match="storage_failure"):
        maintenance.delete_file(store, owner, result.id)
    assert counters(owner) == (8, 0)
    assert (root / "files" / str(owner) / str(result.id)).exists()
    report = maintenance.reconcile(store)
    assert report["operations"][0]["status"] == "storage_failure"
    monkeypatch.setattr(store.fs, "remove", remove)
    assert maintenance.reconcile(store)["operations"][0]["status"] == "deleted"
    assert counters(owner) == (0, 0)
    maintenance.reconcile(store)
    assert counters(owner) == (0, 0)


def test_real_crash_after_unlink_keeps_charge_until_recovery(storage):
    store, owner, _, root = storage
    result = save(store, owner)
    script = """
import os, sys
from pathlib import Path
from uuid import UUID
from app.infrastructure import database
from app.storage.filesystem import FileSystem
from app.storage.service import Storage
from app.storage.maintenance import delete_file
class Crash(FileSystem):
    def remove(self, *args):
        super().remove(*args)
        os._exit(74)
delete_file(Storage(database(), Crash(Path(sys.argv[1]))),
            UUID(sys.argv[2]), UUID(sys.argv[3]))
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(root), str(owner), str(result.id)],
        timeout=20,
    )
    assert child.returncode == 74
    assert counters(owner) == (8, 0)
    assert not (root / "files" / str(owner) / str(result.id)).exists()
    assert maintenance.reconcile(store)["operations"][0]["status"] == "deleted"
    assert counters(owner) == (0, 0)


def test_delete_removes_surviving_staging_link_and_callback_is_atomic(
    storage, monkeypatch
):
    store, owner, _, root = storage
    clean = store.fs.clean
    monkeypatch.setattr(
        store.fs, "clean", lambda *a, **kw: (_ for _ in ()).throw(OSError())
    )
    result = save(store, owner)
    monkeypatch.setattr(store.fs, "clean", clean)
    op = operation(owner)

    def unauthorized(connection):
        connection.execute(
            update(accounts).where(accounts.c.user_id == owner).values(override_bytes=0)
        )
        raise StorageError("forbidden")

    with pytest.raises(StorageError, match="forbidden"):
        maintenance.delete_file(store, owner, result.id, authorize=unauthorized)
    assert counters(owner) == (8, 0)
    with database().connect() as connection:
        assert (
            connection.execute(
                select(accounts.c.override_bytes).where(accounts.c.user_id == owner)
            ).scalar_one()
            is None
        )
    (root / "files" / str(owner) / str(result.id)).unlink()
    assert maintenance.delete_file(store, owner, result.id)
    assert not (root / "staging" / str(op["id"])).exists()
    assert counters(owner) == (0, 0)


def test_reconciliation_is_bounded_reports_corruption_and_never_frees_unclean_bytes(
    storage,
):
    store, owner, _, root = storage
    first = save(store, owner)
    save(store, owner)
    first_page = maintenance.reconcile(store, batch=1)
    assert first_page["next_cursor"]
    second_page = maintenance.reconcile(store, after=first_page["next_cursor"], batch=1)
    assert second_page["next_cursor"] is None
    assert first_page["operations"] != second_page["operations"]
    (root / "files" / str(owner) / str(first.id)).unlink()
    report = maintenance.reconcile(store)
    assert "storage_failure" in [row["status"] for row in report["operations"]]
    assert counters(owner) == (16, 0)
    with database().begin() as connection:
        connection.execute(
            update(accounts).where(accounts.c.user_id == owner).values(used_bytes=1)
        )
    assert maintenance.reconcile_account(store, owner) == "repaired"
    assert counters(owner) == (16, 0)
    with database().begin() as connection:
        connection.execute(
            update(accounts).where(accounts.c.user_id == owner).values(used_bytes=30)
        )
    assert maintenance.reconcile_account(store, owner) == "repair_required"
    assert counters(owner) == (30, 0)
    for invalid in (0, 501, True):
        with pytest.raises(ValueError):
            maintenance.reconcile(store, batch=invalid)


def test_reconcile_expired_staging_and_reject_unready_delete(storage):
    store, owner, _, _ = storage
    op, _ = store._begin(owner, "reserved", "a" * 64, "version", 4)
    assert maintenance.reconcile(store)["operations"][0]["status"] == "busy"
    expire(op)
    assert maintenance.reconcile(store)["operations"][0]["status"] == "recovered"
    assert counters(owner) == (0, 0)
    result = save(store, owner)
    with database().begin() as connection:
        connection.execute(
            update(files).where(files.c.id == result.id).values(state="staged")
        )
    with pytest.raises(StorageError, match="operation_in_progress"):
        maintenance.delete_file(store, owner, result.id)


def test_configuration_capacity_and_private_cli(storage, monkeypatch, capsys):
    store, owner, _, root = storage
    monkeypatch.setenv("STORAGE_ROOT", str(root))
    configured = configuration.configured()
    assert configured.policy.file_bytes == 10 * 1024**2
    for name, value in (
        ("STORAGE_FILE_BYTES", "-1"),
        ("STORAGE_FILE_BYTES", "99999999999999999"),
        ("STORAGE_FILE_BYTES", "1000000000000000"),
        ("STORAGE_LEASE_SECONDS", "0"),
        ("STORAGE_STAGING_BYTES", "9007199254740992"),
        ("STORAGE_ROOT", "/"),
        ("STORAGE_ROOT", "relative"),
    ):
        with monkeypatch.context() as context:
            context.setenv(name, value)
            with pytest.raises(ValueError):
                configuration.configured()
    assert maintenance.main(["capacity"]) == 0
    assert json.loads(capsys.readouterr().out)["disk_available_bytes"] > 0
    assert maintenance.main(["reconcile"]) == 0
    assert json.loads(capsys.readouterr().out)["operations"] == []
    assert maintenance.main(["reconcile", "--batch", "0"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": "storage_maintenance_failed"
    }
    result = save(store, owner)
    (root / "files" / str(owner) / str(result.id)).unlink()
    assert maintenance.main(["reconcile"]) == 1
    assert "/" not in capsys.readouterr().out
    with database().begin() as connection:
        with pytest.raises(ValueError, match="invalid audit data"):
            maintenance.audit(connection, "invalid", owner, contents="never log this")
    child = subprocess.run(
        [sys.executable, "-m", "app.storage.maintenance", "capacity"],
        capture_output=True,
        text=True,
    )
    assert child.returncode == 0 and json.loads(child.stdout)["writable"]


def test_inventory_reports_orphans_without_removing_them(storage, monkeypatch, capsys):
    store, owner, _, root = storage
    save(store, owner)
    assert maintenance.inventory(store)["unknown_entries"] == 0
    orphan = root / "staging" / str(uuid4())
    orphan.write_bytes(b"synthetic orphan")
    unexpected = root / "files" / str(owner) / "unrecognized-name"
    unexpected.write_bytes(b"preserve")
    foreign = root / "files" / str(uuid4())
    foreign.mkdir()
    (root / "staging" / "not-a-uuid").symlink_to(unexpected)
    report = maintenance.inventory(store)
    assert report["unknown_entries"] == 4 and not report["truncated"]
    assert (
        orphan.read_bytes() == b"synthetic orphan"
        and unexpected.read_bytes() == b"preserve"
    )
    assert maintenance.inventory(store, budget=1)["truncated"]
    monkeypatch.setenv("STORAGE_ROOT", str(root))
    assert maintenance.main(["inventory"]) == 1
    output = capsys.readouterr().out
    assert "unrecognized-name" not in output and "synthetic orphan" not in output
    with pytest.raises(ValueError):
        maintenance.inventory(store, budget=0)


def test_account_batches_include_owners_without_operations(
    storage, monkeypatch, capsys
):
    store, owner, _, root = storage
    with database().begin() as connection:
        connection.execute(
            update(accounts).where(accounts.c.user_id == owner).values(used_bytes=10)
        )
    first = maintenance.reconcile_accounts(store, batch=1)
    second = maintenance.reconcile_accounts(store, after=first["next_cursor"], batch=1)
    assert first["next_cursor"] and second["next_cursor"] is None
    rows = first["accounts"] + second["accounts"]
    assert len(rows) == 2 and {row["status"] for row in rows} == {
        "checked",
        "repair_required",
    }
    assert counters(owner) == (10, 0)
    with pytest.raises(ValueError):
        maintenance.reconcile_accounts(store, batch=0)
    monkeypatch.setenv("STORAGE_ROOT", str(root))
    assert maintenance.main(["accounts"]) == 1
    assert "repair_required" in capsys.readouterr().out


def test_reconciliation_repairs_undercount_before_retrying_pending_delete(storage):
    store, owner, _, _ = storage
    result = save(store, owner)
    with database().begin() as connection:
        connection.execute(
            update(files).where(files.c.id == result.id).values(state="pending_delete")
        )
        connection.execute(
            update(accounts).where(accounts.c.user_id == owner).values(used_bytes=1)
        )
    report = maintenance.reconcile(store)
    assert report["operations"][0]["status"] == "storage_failure"
    assert report["accounts"][0]["status"] == "repaired"
    assert counters(owner) == (8, 0)
    assert maintenance.reconcile(store)["operations"][0]["status"] == "deleted"
    assert counters(owner) == (0, 0)
