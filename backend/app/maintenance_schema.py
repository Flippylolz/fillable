"""Durable, content-free progress for the singleton maintenance sweep."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    Table,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.accounts.schema import metadata

TASKS = ("operations", "accounts", "retention", "inventory", "capacity")
CURSORS = ("operations_cursor", "accounts_cursor", "retention_cursor")
state = Table(
    "maintenance_state",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Uuid),
    Column("status", String(16), nullable=False, server_default="idle"),
    Column("started_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("last_success_at", DateTime(timezone=True)),
    Column("interrupted_runs", BigInteger, nullable=False, server_default="0"),
    *(Column(name, Uuid) for name in CURSORS),
    Column("summary", JSONB, nullable=False, server_default="{}"),
    CheckConstraint("id = 1", name="maintenance_singleton"),
    CheckConstraint(
        "status IN ('idle', 'running', 'succeeded', 'failed')",
        name="maintenance_status",
    ),
    CheckConstraint("interrupted_runs >= 0", name="maintenance_interruptions"),
)


def report(connection):
    from sqlalchemy import select

    row = connection.execute(select(state)).mappings().one()
    result = {"status": row["status"], "interrupted_runs": row["interrupted_runs"]}
    for name in ("started_at", "updated_at", "finished_at", "last_success_at"):
        result[name] = row[name].isoformat() if row[name] else None
    for name in ("run_id", *CURSORS):
        result[name] = str(row[name]) if row[name] else None
    # Even malformed historical JSON cannot introduce content into diagnostics.
    source = row["summary"] if isinstance(row["summary"], dict) else {}
    result["summary"] = {
        task: {
            key: value
            for key, value in item.items()
            if key in ("attempts", "examined", "failures", "deferred", "truncated")
            and type(value) is int
            and value >= 0
        }
        for task, item in source.items()
        if task in TASKS and isinstance(item, dict)
    }
    return result
