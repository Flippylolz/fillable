from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
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
from app.documents.export import DocxExport
from app.documents.lease_schema import leases
from app.documents.package import DocxPackage
from app.documents.rebase import correspondence
from app.documents.schema import resources, versions
from app.fields.working import validate_working
from app.infrastructure import database
from app.storage.service import Storage, StorageError


@pytest.mark.parametrize("kind", ["template", "document"])
def test_selected_bytes_reopen_exact_original_edited_and_review_only_pairs(kind):
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
    before = amounts(owner)
    with database().connect() as connection:
        lease_before = dict(connection.execute(select(leases)).mappings().one())
    endpoint = f"/api/documents/{original['id']}"
    current = web.get(endpoint + "/download")
    assert current.headers["x-fillable-version"] == second["saved_version_id"]
    for identity, number in (
        (original["current_version_id"], 1),
        (first["saved_version_id"], 2),
        (second["saved_version_id"], 3),
    ):
        response = web.get(f"{endpoint}/versions/{identity}/download")
        assert response.status_code == 200
        assert response.headers["x-fillable-version"] == identity
        assert response.headers["content-type"] == routes.MIME
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"] == (
            "attachment; filename=\"document.docx\"; filename*=UTF-8''"
            + quote(original["original_filename"], safe="")
        )
        preview = web.get(f"{endpoint}/versions/{identity}/content").json()
        package = DocxPackage(response.content)
        assert package.digest == preview["version"]["digest"]
        assert len(response.content) == preview["version"]["size_bytes"]
        if number == 1:
            assert response.content == DATA and response.content != current.content
            assert package.model == preview["document"]
        else:
            assert response.content == current.content
            model, _ = validate_working(
                preview["document"],
                UUID(identity),
                UUID(original["current_version_id"]),
            )
            assert (
                DocxExport(DocxPackage(DATA)).render(model, DocxPackage(DATA).digest)
                == response.content
            )
            correspondence(model, package)
        assert (
            web.get(f"{endpoint}/versions/{identity}/download").content
            == response.content
        )
    with database().connect() as connection:
        assert dict(connection.execute(select(leases)).mappings().one()) == lease_before
        assert connection.execute(
            select(resources.c.current_version_id)
        ).scalar_one() == UUID(second["saved_version_id"])
    assert amounts(owner) == before


@pytest.mark.parametrize("role", ["user", "admin"])
def test_download_is_owned_scoped_and_never_falls_back_to_current(role):
    _, web, original, _ = start()
    other_resource = upload(web, key="other").json()
    endpoint = f"/api/documents/{original['id']}/versions"
    selected = f"{endpoint}/{original['current_version_id']}/download"
    peer = browser()
    assert peer.get(selected).status_code == 401
    other = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other", role=role),
        PASSWORD,
    )
    assert (
        peer.post(
            "/api/auth/login", json={"email": other.login, "password": PASSWORD}
        ).status_code
        == 200
    )
    assert peer.get(selected).status_code == 404
    for identity in (other_resource["current_version_id"], str(uuid4())):
        assert web.get(f"{endpoint}/{identity}/download").status_code == 404
    assert (
        web.get(
            f"/api/documents/{uuid4()}/versions/{original['current_version_id']}/download"
        ).status_code
        == 404
    )
    assert web.get(f"{endpoint}/invalid/download").status_code == 422
    assert web.delete(f"/api/documents/{original['id']}").status_code == 200
    assert web.get(selected).status_code == 404
    assert web.get(f"/api/documents/{other_resource['id']}/download").status_code == 200


def test_historical_download_corruption_bounds_admission_and_safe_failures(
    document_store, monkeypatch
):
    owner, web, original, _ = start()
    endpoint = f"/api/documents/{original['id']}/versions"
    selected = f"{endpoint}/{original['current_version_id']}/download"
    before = amounts(owner)
    with database().connect() as connection:
        file_id = connection.execute(select(versions.c.file_id)).scalar_one()
    path = document_store / "files" / str(owner.id) / str(file_id)
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    response = web.get(selected)
    assert response.status_code == 503 and "corrupt" not in response.text
    path.write_bytes(DATA)
    # Defensive length check still rejects a short reader even after metadata lookup.
    with monkeypatch.context() as patch:

        @contextmanager
        def short_read(*_args):
            yield BytesIO(b"short")

        patch.setattr(Storage, "read", short_read)
        assert web.get(selected).status_code == 503
    with monkeypatch.context() as patch:
        patch.setattr(history, "ARCHIVE_BYTES", len(DATA) - 1)
        assert web.get(selected).status_code == 503
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
        (SQLAlchemyError("private content"), 503),
    ):
        with monkeypatch.context() as patch:

            def fail(*_args):
                raise failure

            patch.setattr(history, "download", fail)
            response = web.get(selected)
            assert (
                response.status_code == status
                and "private content" not in response.text
            )
        assert web.get(selected).content == DATA  # Every failure releases admission.
    assert amounts(owner) == before


def test_download_filename_cannot_inject_headers():
    _, web, original, _ = start()
    filename = 'Їжак";\r\nX-Injected: true.docx'
    with database().begin() as connection:
        connection.execute(update(resources).values(original_filename=filename))
    response = web.get(
        f"/api/documents/{original['id']}/versions/{original['current_version_id']}/download"
    )
    assert response.status_code == 200
    assert "x-injected" not in response.headers
    assert response.headers["content-disposition"].endswith(quote(filename, safe=""))
