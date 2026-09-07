import json
import subprocess
import sys
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import account_database as account_database
from test_document_persistence import DATA, upload
from test_document_persistence import document_store as document_store
from test_document_restores import restore
from test_document_saves import save, start
from test_template_copies import amounts

from app.documents import retention, retention_cli
from app.documents.retention_schema import settings
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.jobs import worker
from app.jobs.schema import jobs
from app.storage.configuration import configured
from app.storage.maintenance import reconcile
from app.storage.quotas import set_override
from app.storage.schema import audit_events, files
from app.storage.service import Storage, StorageError


@pytest.fixture(autouse=True)
def policy_database(document_store):
    with database().begin() as connection:
        connection.execute(update(settings).values(keep_latest=None, revision=0))
    yield
    with database().begin() as connection:
        connection.execute(update(settings).values(keep_latest=None, revision=0))


def history(count=4):
    owner, web, original, payload = start()
    saved = []
    for number in range(2, count + 1):
        response = save(web, original, payload, f"save-{number}")
        assert response.status_code == 201, response.text
        item = response.json()
        saved.append(item)
        payload["source_version_id"] = item["saved_version_id"]
        if number == 2:
            with database().connect() as connection:
                job = connection.execute(
                    select(jobs.c.id).where(
                        jobs.c.source_version_id == UUID(item["saved_version_id"])
                    )
                ).scalar_one()
            worker.process(str(job), 1)
    return owner, web, original, payload, saved


def selected_file(identity):
    with database().connect() as connection:
        return connection.execute(
            select(versions.c.file_id).where(versions.c.id == UUID(identity))
        ).scalar_one()


def test_policy_is_opt_in_and_prune_preserves_original_current_and_restore_provenance():
    owner, web, original, payload, saved = history()
    source = saved[0]["saved_version_id"]
    restored = restore(web, original, source, payload).json()
    before = amounts(owner)
    endpoint = f"/api/documents/{original['id']}"
    assert retention.prune() == {
        "versions": [],
        "next_cursor": None,
        "bytes_removed": 0,
    }
    set_override(owner.id, 0)
    assert retention.prune()["versions"] == []  # Quota reduction never deletes history.
    assert retention.configure(2).model_dump() == {"keep_latest": 2, "revision": 1}
    assert retention.configure(2).revision == 1
    assert amounts(owner) == before
    assert len(web.get(endpoint + "/versions").json()["items"]) == 5
    first = retention.prune(batch=1)
    assert first["next_cursor"] is not None
    second = retention.prune(batch=1, after=UUID(first["next_cursor"]))
    assert second["next_cursor"] is None
    assert {item["status"] for item in first["versions"] + second["versions"]} == {
        "pruned"
    }
    removed = first["bytes_removed"] + second["bytes_removed"]
    assert removed == 2 * saved[0]["saved_size_bytes"]
    assert amounts(owner) == (before[0] - removed, 0)
    page = web.get(endpoint + "/versions").json()
    assert page["retention"] == {"keep_latest": 2, "revision": 1}
    assert [item["number"] for item in page["items"]] == [5, 4, 1]
    assert page["items"][0]["restored_from_number"] == 2
    assert page["items"][0]["restored_from_version_id"] == source
    assert web.get(f"{endpoint}/versions/{source}/content").status_code == 404
    assert web.get(f"{endpoint}/versions/{source}/download").status_code == 404
    assert (
        web.get(
            f"{endpoint}/versions/{original['current_version_id']}/download"
        ).content
        == DATA
    )
    assert web.get(endpoint + "/content").json()["document"] == payload["document"]
    with database().connect() as connection:
        rows = (
            connection.execute(select(versions).order_by(versions.c.number))
            .mappings()
            .all()
        )
        assert len(rows) == 5 and rows[4]["parent_version_id"] == rows[3]["id"]
        assert rows[1]["document_model"] == {} and rows[1]["field_review"] is None
        assert (
            connection.execute(
                select(jobs.c.field_snapshot).where(
                    jobs.c.source_version_id == UUID(source)
                )
            ).scalar_one()
            is None
        )
        assert connection.execute(
            select(resources.c.current_version_id)
        ).scalar_one() == UUID(restored["saved_version_id"])
    assert retention.prune()["versions"] == []
    retention.configure(None)
    assert web.get(endpoint + "/versions").json()["retention"] == {
        "keep_latest": None,
        "revision": 2,
    }
    assert amounts(owner) == (before[0] - removed, 0)


def test_live_reader_protects_selected_file_until_it_releases():
    owner, _, _, _, saved = history(3)
    identity = saved[0]["saved_version_id"]
    store = configured()
    retention.configure(1)
    before = amounts(owner)
    with store.read(owner.id, selected_file(identity)) as stream:
        result = retention.prune()
        assert result["versions"] == [
            {"version_id": identity, "status": "operation_in_progress"}
        ]
        assert len(stream.read()) == saved[0]["saved_size_bytes"]
        assert amounts(owner) == before
    assert retention.prune()["versions"][0]["status"] == "pruned"
    assert amounts(owner) == (before[0] - saved[0]["saved_size_bytes"], 0)


@pytest.mark.parametrize("change", ["all", "more", "current", "deleted"])
def test_pruning_rechecks_policy_and_current_after_candidate_selection(
    change, monkeypatch
):
    owner, web, original, _, saved = history(3)
    retention.configure(1)
    remove = retention.delete_file

    def changed(*args, **kwargs):
        if change == "all":
            retention.configure(None)
        elif change == "more":
            retention.configure(100)
        elif change == "deleted":
            with database().begin() as connection:
                connection.execute(update(resources).values(state="deleted"))
        else:
            with database().begin() as connection:
                connection.execute(
                    update(resources).values(
                        current_version_id=UUID(saved[0]["saved_version_id"])
                    )
                )
        return remove(*args, **kwargs)

    monkeypatch.setattr(retention, "delete_file", changed)
    before = amounts(owner)
    result = retention.prune()
    assert result["versions"][0]["status"] == "protected_version"
    assert amounts(owner) == before
    if change != "deleted":
        assert (
            web.get(
                f"/api/documents/{original['id']}/versions/{saved[0]['saved_version_id']}/download"
            ).status_code
            == 200
        )


@pytest.mark.parametrize("reference", ["original", "version"])
def test_shared_file_references_are_never_removed(reference):
    owner, web, _, _, saved = history(3)
    other = upload(web, key="other").json()
    file_id = selected_file(saved[0]["saved_version_id"])
    with database().begin() as connection:
        if reference == "original":
            connection.execute(
                update(resources)
                .where(resources.c.id == UUID(other["id"]))
                .values(original_file_id=file_id)
            )
        else:
            connection.execute(
                update(versions)
                .where(versions.c.id == UUID(other["current_version_id"]))
                .values(file_id=file_id)
            )
    retention.configure(1)
    before = amounts(owner)
    assert retention.prune()["versions"][0]["status"] == "protected_version"
    assert amounts(owner) == before


def test_failed_unlink_keeps_charge_and_reconciliation_finishes_cleanup(monkeypatch):
    owner, web, original, _, saved = history(3)
    retention.configure(1)
    store = configured()
    before = amounts(owner)
    file_id = selected_file(saved[0]["saved_version_id"])
    remove = store.fs.remove

    def fail(*args):
        raise OSError("private path")

    with monkeypatch.context() as patch:
        patch.setattr(retention, "configured", lambda: store)
        patch.setattr(store.fs, "remove", fail)
        assert retention.prune()["versions"][0]["status"] == "storage_failure"
    assert amounts(owner) == before
    with database().connect() as connection:
        assert (
            connection.execute(
                select(files.c.state).where(files.c.id == file_id)
            ).scalar_one()
            == "pending_delete"
        )
    assert (
        web.get(
            f"/api/documents/{original['id']}/versions/{saved[0]['saved_version_id']}/content"
        ).status_code
        == 404
    )
    store.fs.remove = remove
    results = reconcile(store)
    assert any(item["status"] == "deleted" for item in results["operations"])
    assert amounts(owner) == (before[0] - saved[0]["saved_size_bytes"], 0)
    assert retention.prune()["versions"] == []


def test_restore_loses_safely_when_pruning_wins_before_finalization(monkeypatch):
    owner, web, original, payload, saved = history(3)
    retention.configure(1)
    finish = Storage._finish

    def prune_before_commit(store, *args):
        assert retention.prune()["versions"][0]["status"] == "pruned"
        return finish(store, *args)

    monkeypatch.setattr(Storage, "_finish", prune_before_commit)
    before = amounts(owner)
    response = restore(web, original, saved[0]["saved_version_id"], payload)
    assert response.status_code == 404, response.text
    assert amounts(owner) == (before[0] - saved[0]["saved_size_bytes"], 0)
    assert (
        web.get(f"/api/documents/{original['id']}").json()["current_version_id"]
        == saved[1]["saved_version_id"]
    )


def test_completed_restore_copy_survives_pruning_its_selected_source(monkeypatch):
    owner, web, original, payload, saved = history(3)
    retention.configure(1)
    remove = retention.delete_file
    restored = None

    def restore_first(*args, **kwargs):
        nonlocal restored
        response = restore(web, original, saved[0]["saved_version_id"], payload)
        assert response.status_code == 201, response.text
        restored = response.json()
        return remove(*args, **kwargs)

    monkeypatch.setattr(retention, "delete_file", restore_first)
    before = amounts(owner)
    assert retention.prune()["versions"][0]["status"] == "pruned"
    assert (
        amounts(owner) == before
    )  # One equal-size restore copy, one old file removed.
    assert (
        web.get(f"/api/documents/{original['id']}/content").json()["resource"][
            "current_version_id"
        ]
        == restored["saved_version_id"]
    )
    page = web.get(f"/api/documents/{original['id']}/versions").json()
    assert page["items"][0]["restored_from_number"] == 2


@pytest.mark.parametrize("value", [0, -1, 10001, True, 1.5, "2"])
def test_policy_values_are_strict_and_bounded(value):
    with pytest.raises(ValueError):
        retention.configure(value)


@pytest.mark.parametrize("batch", [0, -1, 101, True, "1"])
def test_pruning_batches_are_strict_and_bounded(batch):
    with pytest.raises(ValueError):
        retention.prune(batch=batch)


def test_policy_cli_is_audited_private_and_guarded_on_downgrade(capsys, monkeypatch):
    owner, _, _, _, _ = history(3)
    before = amounts(owner)
    assert retention_cli.main(["set", "--keep-latest", "2"]) == 0
    assert json.loads(capsys.readouterr().out) == {"keep_latest": 2, "revision": 1}
    output = subprocess.run(
        [sys.executable, "-m", "app.documents.retention_cli", "show"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(output.stdout) == {"keep_latest": 2, "revision": 1}
    assert amounts(owner) == before
    with database().connect() as connection:
        audit = (
            connection.execute(
                select(audit_events).where(
                    audit_events.c.action == "history_retention_configured"
                )
            )
            .mappings()
            .one()
        )
        assert audit["details"] == {
            "previous_keep_latest": None,
            "keep_latest": 2,
            "policy_revision": 1,
        }
    config = Config("alembic.ini")
    with pytest.raises(RuntimeError, match="refusing destructive downgrade"):
        command.downgrade(config, "0010_revision_provenance")
    assert retention_cli.main(["set", "--keep-latest", "all"]) == 0
    capsys.readouterr()
    assert retention_cli.main(["set", "--keep-latest", "bad"]) == 1
    assert json.loads(capsys.readouterr().out) == {"error": "retention_command_failed"}
    assert retention_cli.main(["prune", "--batch", "0"]) == 1
    capsys.readouterr()
    retention.configure(1)
    assert retention_cli.main(["prune", "--batch", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["versions"][0]["status"] == "pruned"

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private data")

    monkeypatch.setattr(retention, "prune", fail)
    assert retention_cli.main(["prune"]) == 1
    assert json.loads(capsys.readouterr().out) == {"error": "retention_command_failed"}
    with database().begin() as connection:
        connection.execute(update(settings).values(keep_latest=None, revision=0))
    command.downgrade(config, "0010_revision_provenance")
    command.upgrade(config, "head")
    assert amounts(owner)[1] == 0


def test_prune_reports_safe_storage_and_database_failures(monkeypatch):
    _, _, _, _, _ = history(3)
    retention.configure(1)
    for error, expected in (
        (SQLAlchemyError("private data"), "storage_failure"),
        (StorageError("operation_in_progress"), "operation_in_progress"),
    ):

        def fail(*args, **kwargs):
            raise error

        monkeypatch.setattr(retention, "delete_file", fail)
        assert retention.prune()["versions"][0]["status"] == expected
