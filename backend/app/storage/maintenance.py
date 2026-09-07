"""One-shot, bounded maintenance; periodic scheduling is E07.3."""

import argparse
import json
import os
from contextlib import nullcontext
from itertools import islice
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.storage.configuration import configured
from app.storage.schema import accounts, audit_events, files, reservations
from app.storage.service import ACTIVE, StorageError, lock_account, now


def audit(connection, action, owner=None, actor=None, *, event_id=None, **details):
    # Audit data is restricted to opaque IDs and exact counters, never copy/paths.
    if any(
        value is not None and type(value) is not int and not isinstance(value, UUID)
        for value in details.values()
    ):
        raise ValueError("invalid audit data")
    connection.execute(
        insert(audit_events)
        .values(
            id=event_id or uuid4(),
            owner_id=owner,
            actor_id=actor,
            action=action,
            details={
                key: str(value) if isinstance(value, UUID) else value
                for key, value in details.items()
            },
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


def delete_file(store, owner, file_id, *, authorize=None):
    """Domain caller authorizes references in the mark-pending SQL callback."""
    with store.engine.connect() as connection:
        row = (
            connection.execute(
                select(files).where(
                    files.c.id == file_id,
                    files.c.owner_id == owner,
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise StorageError("not_found")
    try:
        with store.fs.lock(row["reservation_id"]):
            with store.engine.begin() as connection:
                lock_account(connection, owner)
                row = (
                    connection.execute(
                        select(files)
                        .where(
                            files.c.id == file_id,
                            files.c.owner_id == owner,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one()
                )
                if row["state"] == "deleted":
                    return False
                if row["state"] not in ("ready", "pending_delete"):
                    raise StorageError("operation_in_progress")
                if row["state"] == "ready":
                    if authorize is not None:
                        authorize(connection)
                    connection.execute(
                        update(files)
                        .where(files.c.id == file_id)
                        .values(
                            state="pending_delete",
                        )
                    )
                    audit(connection, "deletion_requested", owner, file_id=file_id)
            store.fs.remove(row["reservation_id"], owner, file_id)
            with store.engine.begin() as connection:
                account, _ = lock_account(connection, owner)
                connection.execute(
                    update(files)
                    .where(files.c.id == file_id)
                    .values(
                        state="deleted",
                        deleted_at=now(),
                    )
                )
                connection.execute(
                    update(accounts)
                    .where(accounts.c.user_id == owner)
                    .values(
                        used_bytes=account["used_bytes"] - row["size_bytes"],
                    )
                )
                audit(
                    connection,
                    "deletion_completed",
                    owner,
                    file_id=file_id,
                    bytes_removed=row["size_bytes"],
                )
            return True
    except BlockingIOError:
        raise StorageError("operation_in_progress") from None
    except OSError:
        raise StorageError("storage_failure") from None


def reconcile_account(store, owner):
    with store.engine.begin() as connection:
        account, _ = lock_account(connection, owner)
        used = connection.execute(
            select(func.coalesce(func.sum(files.c.size_bytes), 0)).where(
                files.c.owner_id == owner,
                files.c.state.in_(("ready", "pending_delete")),
            )
        ).scalar_one()
        reserved = connection.execute(
            select(func.coalesce(func.sum(reservations.c.allocated_bytes), 0)).where(
                reservations.c.owner_id == owner,
                reservations.c.state.in_(ACTIVE),
            )
        ).scalar_one()
        used, reserved = int(used), int(reserved)
        before_used, before_reserved = account["used_bytes"], account["reserved_bytes"]
        if (used, reserved) == (before_used, before_reserved):
            return "checked"
        # Metadata alone cannot prove that unexpectedly charged bytes disappeared.
        # Raise undercounts; retain overcounts for explicit physical investigation.
        repair_required = used < before_used or reserved < before_reserved
        used, reserved = max(used, before_used), max(reserved, before_reserved)
        connection.execute(
            update(accounts)
            .where(accounts.c.user_id == owner)
            .values(
                used_bytes=used,
                reserved_bytes=reserved,
            )
        )
        audit(
            connection,
            "accounting_discrepancy" if repair_required else "accounting_repaired",
            owner,
            before_used=account["used_bytes"],
            before_reserved=account["reserved_bytes"],
            used=used,
            reserved=reserved,
        )
        return "repair_required" if repair_required else "repaired"


def reconcile(store, *, after=None, batch=100):
    if type(batch) is not int or not 1 <= batch <= 500:
        raise ValueError("invalid reconciliation batch")
    query = select(reservations).order_by(reservations.c.id).limit(batch + 1)
    if after is not None:
        query = query.where(reservations.c.id > after)
    with store.engine.connect() as connection:
        rows = connection.execute(query).mappings().all()
    results, owners = [], set()
    for op in rows[:batch]:
        owner = op["owner_id"]
        owners.add(owner)
        try:
            with store.engine.connect() as connection:
                file = (
                    connection.execute(
                        select(files).where(
                            files.c.reservation_id == op["id"],
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if file is not None and file["state"] == "pending_delete":
                delete_file(store, owner, file["id"])
                status = "deleted"
            elif file is not None and file["state"] == "ready":
                with store.read(owner, file["id"]):
                    pass
                status = "checked" if store.recover(owner, op["id"]) else "busy"
            else:
                status = "recovered" if store.recover(owner, op["id"]) else "busy"
                if status == "recovered" and op["state"] in ACTIVE:
                    with store.engine.begin() as connection:
                        audit(
                            connection,
                            "operation_recovered",
                            owner,
                            event_id=uuid5(
                                NAMESPACE_URL, f"fillable:recovery:{op['id']}"
                            ),
                            operation_id=op["id"],
                            allocated_bytes=op["allocated_bytes"],
                        )
        except (StorageError, SQLAlchemyError) as error:
            status = (
                error.code if isinstance(error, StorageError) else "storage_failure"
            )
            with store.engine.begin() as connection:
                audit(connection, "reconciliation_failed", owner, operation_id=op["id"])
        results.append({"operation_id": str(op["id"]), "status": status})
    account_results = [
        {"owner_id": str(owner), "status": reconcile_account(store, owner)}
        for owner in sorted(owners)
    ]
    return {
        "operations": results,
        "accounts": account_results,
        "next_cursor": str(rows[batch - 1]["id"]) if len(rows) > batch else None,
    }


def capacity(store, *, connection=None):
    with (
        store.engine.connect() if connection is None else nullcontext(connection)
    ) as active:
        allocated, promised = active.execute(
            select(
                func.coalesce(func.sum(reservations.c.allocated_bytes), 0),
                func.coalesce(
                    func.sum(
                        reservations.c.allocated_bytes - reservations.c.written_bytes
                    ),
                    0,
                ),
            ).where(reservations.c.state.in_(ACTIVE))
        ).one()
    available = store.fs.available()
    return {
        "disk_available_bytes": available,
        "active_allocated_bytes": int(allocated),
        "outstanding_bytes": int(promised),
        "staging_limit_bytes": store.policy.staging_bytes,
        "headroom_bytes": store.policy.disk_headroom_bytes,
        "writable": available >= promised + store.policy.disk_headroom_bytes,
    }


def reconcile_accounts(store, *, after=None, batch=100):
    if type(batch) is not int or not 1 <= batch <= 500:
        raise ValueError("invalid reconciliation batch")
    query = select(accounts.c.user_id).order_by(accounts.c.user_id).limit(batch + 1)
    if after is not None:
        query = query.where(accounts.c.user_id > after)
    with store.engine.connect() as connection:
        owners = connection.execute(query).scalars().all()
    return {
        "accounts": [
            {"owner_id": str(owner), "status": reconcile_account(store, owner)}
            for owner in owners[:batch]
        ],
        "next_cursor": str(owners[batch - 1]) if len(owners) > batch else None,
    }


def inventory(store, *, budget=500):
    """Bounded, read-only orphan detection. Never remove unrecognized entries."""
    if type(budget) is not int or not 1 <= budget <= 500:
        raise ValueError("invalid inventory budget")
    remaining, unknown, truncated = budget, 0, False

    def entries(area):
        nonlocal remaining, truncated
        with os.scandir(area) as iterator:
            batch = list(islice(iterator, remaining + 1))
        if len(batch) > remaining:
            truncated = True
        selected = batch[:remaining]
        remaining -= len(selected)
        return [
            (
                entry.name,
                entry.is_file(follow_symlinks=False),
                entry.is_dir(follow_symlinks=False),
            )
            for entry in selected
        ]

    def identity(name):
        try:
            return UUID(name)
        except ValueError:
            return None

    with store.engine.connect() as connection:
        with store.fs.area("staging") as stage:
            for name, regular, _ in entries(stage):
                op = identity(name)
                known = (
                    op is not None
                    and connection.execute(
                        select(reservations.c.id).where(
                            reservations.c.id == op,
                        )
                    ).first()
                    is not None
                )
                unknown += not known or not regular
        with store.fs.area("files") as final:
            owners = entries(final)
        for name, _, is_directory in owners:
            owner = identity(name)
            known = (
                owner is not None
                and connection.execute(
                    select(accounts.c.user_id).where(
                        accounts.c.user_id == owner,
                    )
                ).first()
                is not None
            )
            if not known or not is_directory:
                unknown += 1
                continue
            with store.fs.area("files", owner) as owned:
                for name, regular, _ in entries(owned):
                    file_id = identity(name)
                    known = (
                        file_id is not None
                        and connection.execute(
                            select(files.c.id).where(
                                files.c.id == file_id,
                                files.c.owner_id == owner,
                                files.c.state != "deleted",
                            )
                        ).first()
                        is not None
                    )
                    unknown += not known or not regular
    if unknown:
        with store.engine.begin() as connection:
            audit(connection, "unrecognized_storage_entries", count=unknown)
    return {
        "examined": budget - remaining,
        "unknown_entries": unknown,
        "truncated": truncated,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("reconcile", "accounts", "capacity", "inventory")
    )
    parser.add_argument("--after", type=UUID)
    parser.add_argument("--batch", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        store = configured()
        if args.command == "capacity":
            result = capacity(store)
        elif args.command == "inventory":
            result = inventory(store, budget=args.batch)
        elif args.command == "accounts":
            result = reconcile_accounts(store, after=args.after, batch=args.batch)
        else:
            result = reconcile(store, after=args.after, batch=args.batch)
        print(json.dumps(result))
        if args.command == "inventory" and result["unknown_entries"]:
            return 1
        if args.command in ("reconcile", "accounts") and any(
            item["status"]
            not in ("checked", "recovered", "deleted", "busy", "repaired")
            for item in result.get("operations", []) + result["accounts"]
        ):
            return 1
        return 0
    except (StorageError, SQLAlchemyError, OSError, ValueError, KeyError):
        print(json.dumps({"error": "storage_maintenance_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
