from threading import Event

import pytest
from sqlalchemy import delete, insert, update
from test_accounts import account_database as account_database
from test_document_persistence import DATA
from test_document_persistence import document_store as document_store
from test_document_restores import restore
from test_history_retention import history
from test_template_copies import amounts

from app import maintenance
from app.documents import retention
from app.documents.retention_schema import settings
from app.infrastructure import database
from app.maintenance_schema import state


@pytest.fixture(autouse=True)
def scheduler_database(document_store):
    with database().begin() as connection:
        connection.execute(delete(state))
        connection.execute(insert(state).values(id=1))
        connection.execute(update(settings).values(keep_latest=None, revision=0))
    yield
    with database().begin() as connection:
        connection.execute(delete(state))
        connection.execute(insert(state).values(id=1))
        connection.execute(update(settings).values(keep_latest=None, revision=0))


def test_scheduler_default_all_then_configured_pruning_preserves_original_current():
    owner, web, original, payload, saved = history()
    source = saved[0]["saved_version_id"]
    restore(web, original, source, payload)
    before = amounts(owner)
    endpoint = f"/api/documents/{original['id']}"
    assert maintenance.tick(Event(), batch=100) == "succeeded"
    assert len(web.get(endpoint + "/versions").json()["items"]) == 5
    assert amounts(owner) == before
    retention.configure(2)
    for _ in range(3):
        assert maintenance.tick(Event(), batch=1) == "succeeded"
    assert [
        item["number"] for item in web.get(endpoint + "/versions").json()["items"]
    ] == [5, 4, 1]
    assert amounts(owner) == (before[0] - 2 * saved[0]["saved_size_bytes"], 0)
    assert (
        web.get(
            f"{endpoint}/versions/{original['current_version_id']}/download"
        ).content
        == DATA
    )
    current = web.get(endpoint + "/content").json()
    assert current["document"] == payload["document"]
