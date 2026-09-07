"""Bounded operator diagnostics; never serialize application content or errors."""

import argparse
import json
from typing import NoReturn
from uuid import UUID

from sqlalchemy import case, func, select, tuple_

from app.infrastructure import database
from app.jobs.schema import jobs
from app.storage.configuration import configured
from app.storage.maintenance import capacity
from app.storage.schema import audit_events

STATUSES = ("queued", "running", "succeeded", "failed", "stale")
ACTIONS = frozenset(
    (
        "quota_default_changed",
        "quota_override_changed",
        "deletion_requested",
        "deletion_completed",
        "accounting_discrepancy",
        "accounting_repaired",
        "operation_recovered",
        "reconciliation_failed",
        "unrecognized_storage_entries",
        "document_deletion_requested",
        "history_retention_configured",
        "history_version_pruned",
        "revision_saved",
        "revision_restored",
    )
)
COUNTERS = frozenset(
    (
        "before",
        "after",
        "revision",
        "before_used",
        "before_reserved",
        "used",
        "reserved",
        "allocated_bytes",
        "bytes_removed",
        "count",
        "previous_keep_latest",
        "keep_latest",
        "policy_revision",
        "version_number",
    )
)
IDENTITIES = frozenset(
    (
        "file_id",
        "document_id",
        "version_id",
        "operation_id",
        "parent_version_id",
        "restored_from_version_id",
    )
)


class InvalidRequest(ValueError):
    """Invalid operator arguments, distinct from unavailable runtime configuration."""


def readonly(connection):
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")


def status():
    result = {
        state: {"count": 0, "max_attempt": 0, "expired_leases": 0} for state in STATUSES
    }
    store = configured()
    with database().begin() as connection:
        readonly(connection)
        rows = connection.execute(
            select(
                jobs.c.status,
                func.count(),
                func.max(jobs.c.attempt),
                func.sum(case((jobs.c.lease_until < func.now(), 1), else_=0)),
            ).group_by(jobs.c.status)
        )
        for state, count, attempt, expired in rows:
            result[state] = {
                "count": int(count),
                "max_attempt": int(attempt),
                "expired_leases": int(expired),
            }
        available = capacity(store, connection=connection)
    return {"jobs": result, "capacity": available}


def safe_details(value):
    result: dict[str, str | int | None] = {}
    if not isinstance(value, dict):
        return result
    for key, item in value.items():
        if key in COUNTERS and (item is None or type(item) is int):
            result[key] = item
        elif key in IDENTITIES:
            if item is None:
                result[key] = None
            elif isinstance(item, str):
                try:
                    result[key] = str(UUID(item))
                except ValueError:
                    pass
    return result


def audit_page(*, after=None, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise InvalidRequest("invalid_request")
    if after is not None and not isinstance(after, UUID):
        raise InvalidRequest("invalid_request")
    with database().begin() as connection:
        readonly(connection)
        query = (
            select(audit_events)
            .order_by(audit_events.c.created_at.desc(), audit_events.c.id.desc())
            .limit(limit + 1)
        )
        if after is not None:
            cursor = connection.execute(
                select(audit_events.c.created_at, audit_events.c.id).where(
                    audit_events.c.id == after
                )
            ).first()
            if cursor is None:
                raise InvalidRequest("invalid_request")
            query = query.where(
                tuple_(audit_events.c.created_at, audit_events.c.id)
                < tuple_(cursor.created_at, cursor.id)
            )
        rows = connection.execute(query).mappings().all()
    events = []
    for row in rows[:limit]:
        known = row["action"] in ACTIONS
        events.append(
            {
                "id": str(row["id"]),
                "created_at": row["created_at"].isoformat(),
                "owner_id": str(row["owner_id"]) if row["owner_id"] else None,
                "actor_id": str(row["actor_id"]) if row["actor_id"] else None,
                "action": row["action"] if known else "unknown_event",
                "details": safe_details(row["details"]) if known else {},
            }
        )
    return {
        "events": events,
        "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
    }


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse's default error echoes arbitrary command-line arguments.
        raise InvalidRequest("invalid_request")


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="command", required=True)
        commands.add_parser("status")
        audit = commands.add_parser("audit")
        audit.add_argument("--after", type=UUID)
        audit.add_argument("--limit", type=int, default=50)
        args = parser.parse_args(argv)
        result = (
            status()
            if args.command == "status"
            else audit_page(after=args.after, limit=args.limit)
        )
    except InvalidRequest:
        print(json.dumps({"error": "invalid_request"}))
        return 2
    except Exception:
        print(json.dumps({"error": "diagnostics_unavailable"}))
        return 1
    print(json.dumps(result))
    if args.command == "status" and not result["capacity"]["writable"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
