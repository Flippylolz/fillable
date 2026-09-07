import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, inspect, select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import account
from test_accounts import account_database as account_database
from test_document_persistence import client, upload
from test_document_persistence import document_store as document_store
from test_document_restores import restore
from test_document_saves import save, start

from app import diagnostics
from app.documents import revision_commit
from app.infrastructure import database
from app.jobs.schema import jobs
from app.storage.filesystem import FileSystem
from app.storage.schema import audit_events

PRIVATE = "synthetic-private-filename-field-and-token"


def test_status_reads_only_counters_and_capacity_from_real_job_states(capsys):
    account()
    web = client()
    for state in diagnostics.STATUSES:
        response = upload(web, key=state, title=PRIVATE)
        assert response.status_code == 201
        with database().begin() as connection:
            connection.execute(
                update(jobs)
                .where(jobs.c.document_id == UUID(response.json()["id"]))
                .values(
                    status=state,
                    attempt=2,
                    lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)
                    if state == "running"
                    else None,
                    summary={"private": PRIVATE},
                    field_snapshot={"private": PRIVATE},
                )
            )
    assert diagnostics.main(["status"]) == 0
    output = capsys.readouterr().out
    assert PRIVATE not in output
    result = json.loads(output)
    for state in diagnostics.STATUSES:
        assert result["jobs"][state] == {
            "count": 1,
            "max_attempt": 2,
            "expired_leases": int(state == "running"),
        }
    assert result["capacity"]["writable"] is True
    assert result["capacity"]["active_allocated_bytes"] == 0


def test_empty_status_and_capacity_pressure_are_visible(monkeypatch, capsys):
    assert all(item["count"] == 0 for item in diagnostics.status()["jobs"].values())
    monkeypatch.setenv("STORAGE_DISK_HEADROOM_BYTES", "100")
    monkeypatch.setattr(FileSystem, "available", lambda self: 0)
    assert diagnostics.status()["capacity"]["writable"] is False
    assert diagnostics.main(["status"]) == 1
    assert json.loads(capsys.readouterr().out)["capacity"]["writable"] is False


def test_chronological_audit_pages_redact_unknown_data_and_advance_across_ties():
    base = datetime.now(timezone.utc)
    ids = [UUID(int=index) for index in range(1, 6)]
    with database().begin() as connection:
        connection.execute(delete(audit_events))
        for index, identity in enumerate(ids):
            connection.execute(
                insert(audit_events).values(
                    id=identity,
                    created_at=base + timedelta(seconds=index // 2),
                    action="quota_default_changed" if index != 3 else PRIVATE,
                    details={
                        "before": 5,
                        "after": None,
                        "revision": True,
                        "document_id": str(uuid4()),
                        "file_id": PRIVATE,
                        "version_id": None,
                        "operation_id": 12,
                        PRIVATE: PRIVATE,
                    },
                )
            )
    first = diagnostics.audit_page(limit=2)
    assert [item["id"] for item in first["events"]] == [str(ids[4]), str(ids[3])]
    assert first["events"][1]["action"] == "unknown_event"
    assert first["events"][1]["details"] == {}
    assert set(first["events"][0]["details"]) == {
        "before",
        "after",
        "document_id",
        "version_id",
    }
    assert PRIVATE not in json.dumps(first)
    with database().begin() as connection:
        connection.execute(
            insert(audit_events).values(
                id=uuid4(),
                created_at=base + timedelta(seconds=10),
                action="quota_default_changed",
                details=[PRIVATE],
            )
        )
    assert diagnostics.audit_page(limit=1)["events"][0]["details"] == {}
    second = diagnostics.audit_page(after=UUID(first["next_cursor"]), limit=2)
    third = diagnostics.audit_page(after=UUID(second["next_cursor"]), limit=2)
    assert [item["id"] for item in second["events"] + third["events"]] == list(
        map(str, ids[2::-1])
    )
    assert third["next_cursor"] is None
    assert diagnostics.audit_page(after=ids[0])["events"] == []


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": True},
        {"after": "private"},
        {"after": uuid4()},
    ],
)
def test_audit_rejects_invalid_bounds_and_missing_cursors(options):
    with pytest.raises(ValueError, match="invalid_request"):
        diagnostics.audit_page(**options)


@pytest.mark.parametrize(
    "args",
    [
        [],
        [PRIVATE],
        ["audit", "--after", PRIVATE],
        ["audit", "--limit", PRIVATE],
        ["audit", "--limit", "0"],
    ],
)
def test_cli_usage_errors_never_echo_arguments(args, capsys):
    assert diagnostics.main(args) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"error": "invalid_request"}
    assert captured.err == "" and PRIVATE not in captured.out


def test_cli_audit_and_process_entrypoint(capsys):
    assert diagnostics.main(["audit", "--limit", "100"]) == 0
    assert json.loads(capsys.readouterr().out) == {"events": [], "next_cursor": None}
    completed = subprocess.run(
        [sys.executable, "-m", "app.diagnostics", "audit"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(completed.stdout) == {"events": [], "next_cursor": None}


@pytest.mark.parametrize(
    "error",
    [
        OSError(PRIVATE),
        SQLAlchemyError(PRIVATE),
        RuntimeError(PRIVATE),
        ValueError(PRIVATE),
    ],
)
def test_cli_failures_have_a_content_free_exit(error, monkeypatch, capsys):
    def fail():
        raise error

    monkeypatch.setattr(diagnostics, "status", fail)
    assert diagnostics.main(["status"]) == 1
    assert capsys.readouterr().out.strip() == '{"error": "diagnostics_unavailable"}'


def test_revision_audits_are_atomic_and_exact_replays_do_not_duplicate(monkeypatch):
    owner, web, original, payload = start()
    real_audit = revision_commit.audit

    def fail(*args, **kwargs):
        raise SQLAlchemyError(PRIVATE)

    monkeypatch.setattr(revision_commit, "audit", fail)
    assert save(web, original, payload, "failed").status_code == 503
    assert diagnostics.audit_page()["events"] == []
    monkeypatch.setattr(revision_commit, "audit", real_audit)
    first = save(web, original, payload, "saved")
    assert first.status_code == 201
    assert save(web, original, payload, "saved").status_code == 201
    payload["source_version_id"] = first.json()["saved_version_id"]
    restored = restore(web, original, original["current_version_id"], payload)
    assert restored.status_code == 201
    assert (
        restore(web, original, original["current_version_id"], payload).status_code
        == 201
    )
    events = diagnostics.audit_page()["events"]
    assert [item["action"] for item in events] == [
        "revision_restored",
        "revision_saved",
    ]
    assert all(
        item["owner_id"] == str(owner.id) and item["actor_id"] == str(owner.id)
        for item in events
    )
    assert (
        events[0]["details"]["restored_from_version_id"]
        == original["current_version_id"]
    )
    assert [item["details"]["version_number"] for item in events] == [3, 2]


def test_audit_index_upgrade_and_downgrade_preserve_events():
    identity = uuid4()
    with database().begin() as connection:
        connection.execute(
            insert(audit_events).values(
                id=identity,
                action="quota_default_changed",
                details={"after": 1},
            )
        )
    config = Config("alembic.ini")
    command.downgrade(config, "0011_history_retention")
    assert "storage_audit_chronology" not in {
        item["name"] for item in inspect(database()).get_indexes("storage_audit")
    }
    command.upgrade(config, "head")
    assert "storage_audit_chronology" in {
        item["name"] for item in inspect(database()).get_indexes("storage_audit")
    }
    with database().connect() as connection:
        assert connection.execute(select(audit_events.c.id)).scalars().all() == [
            identity
        ]
