import os
import signal
import subprocess
import sys
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from test_storage_service import counters, save
from test_storage_service import setup as setup

from app import diagnostics, maintenance
from app.infrastructure import database
from app.maintenance_schema import TASKS, report, state
from app.storage import maintenance as storage_maintenance
from app.storage.schema import audit_events
from app.storage.service import StorageError


@pytest.fixture
def storage(setup, monkeypatch):
    store, owner, other, root = setup
    monkeypatch.setenv("STORAGE_ROOT", str(root))
    monkeypatch.setenv("STORAGE_DISK_HEADROOM_BYTES", "0")
    with database().begin() as connection:
        connection.execute(delete(state))
        connection.execute(insert(state).values(id=1))
    yield setup
    with database().begin() as connection:
        connection.execute(delete(audit_events))
        connection.execute(delete(state))
        connection.execute(insert(state).values(id=1))


def status():
    with database().connect() as connection:
        return report(connection)


def fail(*args, **kwargs):
    raise SQLAlchemyError("synthetic-private-token-path")


def test_real_singleton_competition_close_and_old_generation_fence(storage):
    with maintenance.singleton() as first:
        assert first is not None
        assert maintenance.tick(Event()) == "busy"
    assert maintenance.tick(Event()) == "succeeded"
    completed = status()
    assert completed["last_success_at"]
    assert set(completed["summary"]) == set(TASKS)
    with database().begin() as connection:
        with pytest.raises(maintenance.LostRun):
            maintenance.fence(connection, uuid4(), status="failed")
    assert status() == completed
    with maintenance.singleton() as next_guard:
        assert next_guard is not None


def test_real_failed_unlink_keeps_charge_advances_then_recovers(storage, monkeypatch):
    store, owner, _, root = storage
    first = save(store, owner)
    save(store, owner, data=b"second")
    remove = type(store.fs).remove
    monkeypatch.setattr(
        type(store.fs), "remove", lambda *args: (_ for _ in ()).throw(OSError())
    )
    with pytest.raises(StorageError):
        storage_maintenance.delete_file(store, owner, first.id)
    assert counters(owner) == (14, 0)
    for _ in range(3):
        maintenance.tick(Event(), batch=1)
    assert counters(owner) == (14, 0)
    assert (root / "files" / str(owner) / str(first.id)).exists()
    monkeypatch.setattr(type(store.fs), "remove", remove)
    for _ in range(3):
        maintenance.tick(Event(), batch=1)
    assert counters(owner) == (6, 0)
    assert not (root / "files" / str(owner) / str(first.id)).exists()
    assert status()["operations_cursor"] is None or UUID(status()["operations_cursor"])


def test_retry_budget_continues_independent_tasks_and_safe_failure(
    storage, monkeypatch, capsys
):
    calls = []
    original = maintenance.perform

    def perform(name, *args):
        calls.append(name)
        if name == "operations":
            fail()
        return original(name, *args)

    class Stop:
        def is_set(self):
            return False

        def wait(self, seconds):
            assert seconds in (1, 2)
            return False

    monkeypatch.setattr(maintenance, "perform", perform)
    assert maintenance.run(Stop(), once=True) == 1
    assert calls.count("operations") == 3
    assert calls[-1] == "capacity"
    assert status()["summary"]["operations"] == {
        "attempts": 3,
        "examined": 0,
        "failures": 1,
    }
    assert diagnostics.main(["status"]) == 1
    assert "synthetic-private" not in capsys.readouterr().out
    monkeypatch.setattr(maintenance, "perform", original)
    assert maintenance.tick(Event()) == "succeeded"
    assert diagnostics.main(["status"]) == 0


def test_stop_during_retry_and_before_first_task(storage, monkeypatch):
    stop = Event()

    def stopped(*args):
        stop.set()
        fail()

    monkeypatch.setattr(maintenance, "perform", stopped)
    assert maintenance.tick(stop) == "failed"
    assert status()["summary"]["operations"]["attempts"] == 1
    assert maintenance.tick(stop) == "failed"
    assert maintenance.run(stop) == 0
    assert status()["last_success_at"] is None


def test_unknown_entries_are_reported_never_removed_and_diagnostics_redact(storage):
    _, _, _, root = storage
    unknown = root / "staging" / "synthetic-private-name"
    unknown.write_bytes(b"retained")
    assert maintenance.tick(Event()) == "failed"
    assert unknown.read_bytes() == b"retained"
    with database().begin() as connection:
        connection.execute(
            update(state).values(
                summary={
                    "private": {"examined": 5},
                    "operations": {
                        "examined": 2,
                        "private": "secret",
                        "failures": True,
                        "deferred": -1,
                    },
                    "accounts": "secret",
                }
            )
        )
    assert status()["summary"] == {"operations": {"examined": 2}}
    with database().begin() as connection:
        connection.execute(update(state).values(summary=[]))
    assert status()["summary"] == {}


def test_real_process_crash_releases_singleton_and_counts_interruption(storage):
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os
from threading import Event
from app import maintenance
maintenance.perform = lambda *args: os._exit(74)
maintenance.tick(Event())
""",
        ],
        timeout=20,
    )
    assert child.returncode == 74
    assert status()["status"] == "running"
    assert maintenance.tick(Event()) == "succeeded"
    assert status()["interrupted_runs"] == 1


def test_migration_preserves_existing_files_and_refuses_used_state_downgrade(storage):
    store, owner, _, _ = storage
    retained = save(store, owner)
    command.downgrade(Config("alembic.ini"), "0012_audit_chronology")
    command.upgrade(Config("alembic.ini"), "head")
    with store.read(owner, retained.id) as stream:
        assert stream.read() == b"original"
    assert counters(owner) == (8, 0)
    maintenance.tick(Event())
    with pytest.raises(RuntimeError, match="Maintenance history exists"):
        command.downgrade(Config("alembic.ini"), "0012_audit_chronology")


def test_failed_account_and_audit_do_not_starve_following_rows(storage, monkeypatch):
    store, owner, _, _ = storage
    save(store, owner)
    monkeypatch.setattr(storage_maintenance, "reconcile_account", fail)
    assert all(
        item["status"] == "storage_failure"
        for item in storage_maintenance.reconcile_accounts(store)["accounts"]
    )
    monkeypatch.setattr(store, "read", fail)
    monkeypatch.setattr(storage_maintenance, "audit", fail)
    result = storage_maintenance.reconcile(store)
    assert result["operations"][0]["status"] == "storage_failure"
    assert result["accounts"][0]["status"] == "storage_failure"


def test_actual_pg_lock_timeout_is_bounded_and_cursor_can_advance(storage, monkeypatch):
    store, owner, _, _ = storage
    from sqlalchemy import create_engine

    from app.storage.schema import accounts

    bounded = create_engine(
        database().url,
        connect_args={"options": "-c lock_timeout=100 -c statement_timeout=1000"},
    )
    store.engine = bounded
    try:
        with database().begin() as blocked:
            blocked.execute(
                select(accounts).where(accounts.c.user_id == owner).with_for_update()
            )
            result = storage_maintenance.reconcile_accounts(store)
            by_id = {item["owner_id"]: item["status"] for item in result["accounts"]}
            assert by_id[str(owner)] == "storage_failure"
            assert "checked" in by_id.values()
        assert all(
            item["status"] == "checked"
            for item in storage_maintenance.reconcile_accounts(store)["accounts"]
        )
    finally:
        bounded.dispose()


def test_bounded_configuration_loop_exception_and_signal_stop(
    storage, monkeypatch, capsys
):
    assert maintenance.main(["synthetic-private"]) == 2
    for setting, value in (
        ("MAINTENANCE_BATCH", "0"),
        ("MAINTENANCE_BATCH", "101"),
        ("MAINTENANCE_INTERVAL_SECONDS", "9"),
        ("MAINTENANCE_INTERVAL_SECONDS", "wrong"),
    ):
        with monkeypatch.context() as patch:
            patch.setenv(setting, value)
            assert maintenance.main([]) == 2
    with pytest.raises(ValueError):
        maintenance.tick(Event(), batch=True)
    assert maintenance.main(["--once"]) == 0
    monkeypatch.setattr(maintenance, "tick", fail)
    assert maintenance.run(Event(), once=True) == 1

    def stop_tick(stop, **kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        return "succeeded"

    monkeypatch.setattr(maintenance, "tick", stop_tick)
    assert maintenance.main([]) == 0
    assert "synthetic-private" not in capsys.readouterr().out


def test_guard_loss_or_configuration_failure_stays_visible(storage, monkeypatch):
    monkeypatch.setattr(maintenance, "configured", fail)
    assert maintenance.tick(Event()) == "failed"
    monkeypatch.setattr(maintenance, "fence", fail)
    assert maintenance.tick(Event()) == "failed"
    assert status()["status"] == "running"


def test_persisted_operation_cursor_passes_poisoned_entry_and_wraps(storage):
    store, owner, _, root = storage
    for _ in range(3):
        save(store, owner)
    from app.storage.schema import reservations

    with database().connect() as connection:
        rows = (
            connection.execute(select(reservations).order_by(reservations.c.id))
            .mappings()
            .all()
        )
    damaged = root / "files" / str(owner) / str(rows[0]["file_id"])
    damaged.chmod(0o600)
    damaged.write_bytes(b"damaged!")
    assert maintenance.tick(Event(), batch=1) == "failed"
    assert status()["operations_cursor"] == str(rows[0]["id"])
    assert maintenance.tick(Event(), batch=1) == "succeeded"
    assert status()["operations_cursor"] == str(rows[1]["id"])
    assert maintenance.tick(Event(), batch=1) == "succeeded"
    assert status()["operations_cursor"] is None
    assert maintenance.tick(Event(), batch=1) == "failed"
    assert counters(owner) == (24, 0)
    assert damaged.read_bytes() == b"damaged!"


def test_real_guard_connection_loss_leaves_replayable_state(storage, monkeypatch):
    from contextlib import contextmanager

    original = maintenance.singleton
    held = []

    @contextmanager
    def capture():
        with original() as connection:
            held.append(connection)
            yield connection

    perform = maintenance.perform

    def disconnect(name, *args):
        result = perform(name, *args)
        pid = held[0].exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
        with database().begin() as killer:
            killer.exec_driver_sql(f"SELECT pg_terminate_backend({pid})")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(maintenance, "singleton", capture)
        patch.setattr(maintenance, "perform", disconnect)
        assert maintenance.tick(Event()) == "failed"
    assert maintenance.tick(Event()) == "succeeded"
    assert status()["last_success_at"]
