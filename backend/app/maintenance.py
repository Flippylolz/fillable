"""Scheduled, bounded reconciliation using the existing idempotent storage paths."""

import json
import os
import signal
import sys
from contextlib import contextmanager
from threading import Event
from uuid import UUID, uuid4

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.documents.retention import prune
from app.infrastructure import database
from app.maintenance_schema import TASKS, state
from app.storage.configuration import configured
from app.storage.maintenance import capacity, inventory, reconcile, reconcile_accounts
from app.storage.service import StorageError

# Application-scoped advisory key, distinct from all domain/account row locks.
LOCK_KEY = 0x46494C4C4D41494E
SUCCESS = frozenset(
    ("checked", "repaired", "deleted", "recovered", "pruned", "already_deleted")
)
DEFERRED = frozenset(("busy", "operation_in_progress", "protected_version"))


class LostRun(RuntimeError):
    pass


@contextmanager
def singleton():
    # NullPool physically closes the dedicated session, including on exceptions.
    # Domain work uses separate short transactions, never this lock connection.
    engine = create_engine(
        database().url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 2},
    )
    try:
        with engine.connect() as connection:
            acquired = connection.exec_driver_sql(
                f"SELECT pg_try_advisory_lock({LOCK_KEY})"
            ).scalar_one()
            yield connection if acquired else None
    finally:
        engine.dispose()


def fence(connection, run_id, **values):
    changed = connection.execute(
        update(state)
        .where(state.c.id == 1, state.c.run_id == run_id)
        .values(updated_at=func.now(), **values)
    )
    if changed.rowcount != 1:
        raise LostRun()


def summarize(result, keys):
    items = [item for key in keys for item in result[key]]
    return {
        "examined": len(items),
        "failures": sum(item["status"] not in SUCCESS | DEFERRED for item in items),
        "deferred": sum(item["status"] in DEFERRED for item in items),
    }


def perform(name, store, cursor, batch):
    if name == "operations":
        result = reconcile(store, after=cursor, batch=batch)
        return summarize(result, ("operations", "accounts")), result["next_cursor"]
    if name == "accounts":
        result = reconcile_accounts(store, after=cursor, batch=batch)
        return summarize(result, ("accounts",)), result["next_cursor"]
    if name == "retention":
        result = prune(after=cursor, batch=batch)
        return summarize(result, ("versions",)), result["next_cursor"]
    if name == "inventory":
        result = inventory(store, budget=batch)
        return {
            "examined": result["examined"],
            "failures": result["unknown_entries"],
            "truncated": int(result["truncated"]),
        }, None
    result = capacity(store)
    return {"examined": 1, "failures": int(not result["writable"])}, None


def tick(stop, *, batch=20):
    if type(batch) is not int or not 1 <= batch <= 100:
        raise ValueError("invalid batch")
    with singleton() as guard:
        if guard is None:
            return "busy"
        pid = guard.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
        previous = guard.execute(select(state)).mappings().one()
        run_id = uuid4()
        guard.execute(
            update(state)
            .where(state.c.id == 1)
            .values(
                run_id=run_id,
                status="running",
                started_at=func.now(),
                updated_at=func.now(),
                finished_at=None,
                interrupted_runs=previous["interrupted_runs"]
                + int(previous["status"] == "running"),
            )
        )
        summaries = {}
        try:
            store = configured()
            for name in TASKS:
                if stop.is_set():
                    break
                cursor_name = f"{name}_cursor"
                cursor = previous.get(cursor_name)
                for attempt in range(1, 4):
                    try:
                        # A reconnected guard no longer owns the lock.
                        if (
                            guard.exec_driver_sql(
                                "SELECT pg_backend_pid()"
                            ).scalar_one()
                            != pid
                        ):
                            raise LostRun()
                        summary, following = perform(name, store, cursor, batch)
                        break
                    except (SQLAlchemyError, OSError, StorageError):
                        summary, following = {"examined": 0, "failures": 1}, cursor
                        if attempt == 3 or stop.wait(attempt):
                            break
                summaries[name] = {**summary, "attempts": attempt}
                values: dict[str, object] = {"summary": summaries}
                if cursor_name in previous:
                    values[cursor_name] = (
                        UUID(following) if isinstance(following, str) else following
                    )
                fence(guard, run_id, **values)
            succeeded = len(summaries) == len(TASKS) and all(
                item["failures"] == 0 for item in summaries.values()
            )
            outcome = "succeeded" if succeeded else "failed"
            values = {"status": outcome, "finished_at": func.now()}
            if succeeded:
                values["last_success_at"] = func.now()
            fence(guard, run_id, **values)
            return outcome
        except Exception:
            # Persist only fixed state. Losing the guard/fence leaves a visible
            # unfinished run for the next singleton to count and safely replay.
            try:
                fence(guard, run_id, status="failed", finished_at=func.now())
            except Exception:
                pass
            return "failed"


def run(stop, *, interval=60, batch=20, once=False):
    while not stop.is_set():
        try:
            outcome = tick(stop, batch=batch)
        except Exception:
            outcome = "failed"
        print(json.dumps({"event": "maintenance_tick", "status": outcome}), flush=True)
        if once:
            return int(outcome == "failed")
        if stop.wait(interval):
            break
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv not in ([], ["--once"]):
            raise ValueError()
        interval = int(os.environ.get("MAINTENANCE_INTERVAL_SECONDS", "60"))
        batch = int(os.environ.get("MAINTENANCE_BATCH", "20"))
        if not 10 <= interval <= 3600 or not 1 <= batch <= 100:
            raise ValueError()
    except ValueError:
        print(json.dumps({"error": "invalid_maintenance_configuration"}))
        return 2
    stop = Event()
    previous = {
        sig: signal.signal(sig, lambda *_: stop.set())
        for sig in (signal.SIGTERM, signal.SIGINT)
    }
    try:
        return run(stop, interval=interval, batch=batch, once=bool(argv))
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
