from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import PASSWORD, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, upload
from test_document_persistence import document_store as document_store
from test_document_saves import save, start
from test_template_copies import amounts

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput
from app.documents import history, routes
from app.documents.lease_schema import leases
from app.documents.package import ARCHIVE_BYTES, DocxPackage
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.storage.schema import files
from app.storage.service import StorageError


@pytest.mark.parametrize("kind", ["template", "document"])
def test_history_lists_and_opens_exact_retained_pairs_without_writes(kind):
    owner, web, original, payload = start(kind)
    first = save(web, original, payload).json()
    changed = deepcopy(payload)
    changed["source_version_id"] = first["saved_version_id"]
    next(
        item
        for item in changed["document"]["attrs"]["review"]["items"]
        if item["decision"] == "proposed"
    )["decision"] = "dismissed"
    second = save(web, first["resource"], changed, "next").json()
    url = f"/api/documents/{original['id']}/versions"
    before = amounts(owner)
    with database().connect() as connection:
        lease_before = dict(connection.execute(select(leases)).mappings().one())
    response = web.get(url, params={"limit": 2})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    page = response.json()
    assert page["current_version_id"] == second["saved_version_id"]
    assert page["next_before"] == 2
    assert [item["number"] for item in page["items"]] == [3, 2]
    assert [item["is_current"] for item in page["items"]] == [True, False]
    assert all(
        "document" not in item and "field_review" not in item for item in page["items"]
    )
    assert all(
        item["created_at"]
        and item["size_bytes"] == first["saved_size_bytes"]
        and item["digest"] == first["saved_digest"]
        for item in page["items"]
    )
    last = web.get(url, params={"limit": 2, "before": page["next_before"]}).json()
    assert last["next_before"] is None
    assert [item["number"] for item in last["items"]] == [1]
    assert web.get(url, params={"before": 1}).json()["items"] == []
    for identity, expected, number in (
        (original["current_version_id"], DocxPackage(DATA).model, 1),
        (first["saved_version_id"], payload["document"], 2),
        (second["saved_version_id"], changed["document"], 3),
    ):
        preview = web.get(f"{url}/{identity}/content")
        assert preview.status_code == 200
        assert preview.headers["cache-control"] == "no-store"
        assert preview.json()["document"] == expected
        assert preview.json()["version"]["id"] == identity
        assert preview.json()["version"]["number"] == number
        assert preview.json()["version"]["is_current"] == (number == 3)
    with database().connect() as connection:
        assert dict(connection.execute(select(leases)).mappings().one()) == lease_before
        assert connection.execute(
            select(resources.c.current_version_id)
        ).scalar_one() == UUID(second["saved_version_id"])
    assert amounts(owner) == before


def test_history_current_marker_and_rows_share_a_snapshot_during_a_real_save():
    _, web, original, payload = start()
    triggered = False
    with ThreadPoolExecutor(max_workers=1) as pool:

        def concurrent_save(_connection, _cursor, statement, *_args):
            nonlocal triggered
            if not triggered and statement.startswith(
                "SELECT documents.current_version_id"
            ):
                triggered = True
                result = pool.submit(save, web, original, payload, "concurrent").result(
                    timeout=10
                )
                assert result.status_code == 201

        event.listen(database(), "after_cursor_execute", concurrent_save)
        try:
            page = web.get(f"/api/documents/{original['id']}/versions").json()
        finally:
            event.remove(database(), "after_cursor_execute", concurrent_save)
    assert triggered
    assert page["current_version_id"] == original["current_version_id"]
    assert [(item["number"], item["is_current"]) for item in page["items"]] == [
        (1, True)
    ]
    later = web.get(f"/api/documents/{original['id']}/versions").json()
    assert [(item["number"], item["is_current"]) for item in later["items"]] == [
        (2, True),
        (1, False),
    ]


def test_history_owner_resource_revision_and_deletion_boundaries():
    _, web, original, _ = start()
    another = upload(web, key="another").json()
    url = f"/api/documents/{original['id']}/versions"
    selected = f"{url}/{original['current_version_id']}/content"
    peer = browser()
    for path in (url, selected):
        assert peer.get(path).status_code == 401
    other = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    assert (
        peer.post(
            "/api/auth/login", json={"email": other.email, "password": PASSWORD}
        ).status_code
        == 200
    )
    for path in (url, selected):
        assert peer.get(path).status_code == 404
    assert web.get(f"{url}/{another['current_version_id']}/content").status_code == 404
    assert web.get(f"{url}/{uuid4()}/content").status_code == 404
    assert web.get(f"/api/documents/{uuid4()}/versions").status_code == 404
    assert (
        web.get(
            f"/api/documents/{another['id']}/versions/{original['current_version_id']}/content"
        ).status_code
        == 404
    )
    assert web.delete(f"/api/documents/{original['id']}").status_code == 200
    for path in (url, selected):
        assert web.get(path).status_code == 404
    assert web.get(f"/api/documents/{another['id']}/versions").status_code == 200


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": "bad"},
        {"before": 0},
        {"before": -1},
        {"before": "bad"},
    ],
)
def test_history_pagination_is_bounded(query):
    _, web, original, _ = start()
    response = web.get(f"/api/documents/{original['id']}/versions", params=query)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_preview_checks_bytes_admission_and_content_free_failures(
    document_store, monkeypatch
):
    owner, web, original, _ = start()
    url = f"/api/documents/{original['id']}/versions"
    selected = f"{url}/{original['current_version_id']}/content"
    with database().connect() as connection:
        file_id = connection.execute(select(versions.c.file_id)).scalar_one()
    before = amounts(owner)
    with database().begin() as connection:
        connection.execute(
            update(files)
            .where(files.c.id == file_id)
            .values(size_bytes=ARCHIVE_BYTES + 1)
        )
    assert web.get(selected).status_code == 503
    with database().begin() as connection:
        connection.execute(
            update(files).where(files.c.id == file_id).values(size_bytes=len(DATA))
        )
    path = document_store / "files" / str(owner.id) / str(file_id)
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    assert web.get(selected).status_code == 503
    assert (
        web.get(url).status_code == 200
    )  # Metadata does not pretend to verify every file.
    routes.DOWNLOAD_SLOTS.acquire()
    routes.DOWNLOAD_SLOTS.acquire()
    try:
        assert web.get(selected).status_code == 409
    finally:
        routes.DOWNLOAD_SLOTS.release()
        routes.DOWNLOAD_SLOTS.release()
    for failure, status in (
        (StorageError("not_found"), 404),
        (StorageError("operation_in_progress"), 409),
        (SQLAlchemyError("private text"), 503),
    ):

        def fail(*_args):
            raise failure

        monkeypatch.setattr(history, "content", fail)
        response = web.get(selected)
        assert response.status_code == status and "private text" not in response.text
    monkeypatch.setattr(history, "listing", fail)
    response = web.get(url)
    assert response.status_code == 503 and "private text" not in response.text
    assert amounts(owner) == before
