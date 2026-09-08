"""Authenticated synthetic deployment checks; never print remote data or secrets."""

import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


def checked(client, method, path, **kwargs):
    # Retry only an unchanged idempotent write while a worker holds a file reader.
    for _ in range(40):
        response = client.request(method, path, **kwargs)
        if (
            response.status_code == 409
            and response.json().get("error", {}).get("code") == "operation_in_progress"
            and "Idempotency-Key" in kwargs.get("headers", {})
        ):
            time.sleep(0.5)
            continue
        response.raise_for_status()
        return response
    raise ValueError("Synthetic operation remained busy")


def login(client, identifier, password):
    bootstrap = checked(client, "GET", "/api/auth/session")
    client.headers["X-CSRF-Token"] = bootstrap.json()["csrf_token"]
    response = client.post(
        "/api/auth/login", json={"login": identifier, "password": password}
    )
    if response.status_code == 401:
        return False
    response.raise_for_status()
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "; secure" not in cookie
    session = response.json()
    assert session["user"]["login"] == identifier.strip().casefold()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return True


def smoke(client, source, fixtures):
    checked(client, "GET", "/api/ready")
    checked(client, "GET", "/")
    # Neither an incorrect origin nor an incorrect CSRF token may end this session.
    for headers in (
        {"Origin": "http://invalid.test:3200"},
        {"X-CSRF-Token": "invalid"},
    ):
        assert client.post("/api/auth/logout", headers=headers).status_code == 403
    original = (fixtures / "client-intake-uk-v1.docx").read_bytes()
    identifier = uuid4().hex
    uploaded = checked(
        client,
        "POST",
        "/api/documents",
        content=original,
        headers={
            "Content-Type": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            "Idempotency-Key": "release-upload-" + identifier,
            "X-Upload-Metadata": base64.b64encode(
                json.dumps(
                    {
                        "kind": "template",
                        "filename": "Перевірка.docx",
                        "title": "Перевірка розгортання " + identifier[:8],
                    },
                    ensure_ascii=False,
                ).encode()
            ).decode(),
        },
    ).json()
    endpoint = "/api/documents/" + uploaded["id"]
    original_version = uploaded["current_version_id"]
    for _ in range(120):
        processing = checked(client, "GET", endpoint + "/processing").json()
        if processing["status"] == "succeeded":
            break
        time.sleep(0.5)
    else:
        raise ValueError("Synthetic processing did not finish")
    tab = str(uuid4())
    lease = checked(
        client,
        "POST",
        endpoint + "/editing-lease",
        json={
            "action": "acquire",
            "client_id": tab,
            "source_version_id": original_version,
            "lease_id": None,
        },
    ).json()
    model = json.loads((fixtures / "working-review.json").read_text())
    model["attrs"]["review"]["sourceVersion"] = original_version
    saved = checked(
        client,
        "POST",
        endpoint + "/versions",
        json={
            "client_id": tab,
            "lease_id": lease["lease_id"],
            "source_version_id": original_version,
            "document": model,
        },
        headers={"Idempotency-Key": "release-save-" + identifier},
    ).json()
    assert saved["saved_number"] == 2
    current = checked(client, "GET", endpoint + "/content").json()
    assert current["document"] == model
    current_bytes = checked(client, "GET", endpoint + "/download").content
    assert current_bytes != original
    assert hashlib.sha256(current_bytes).hexdigest() == saved["resource"]["digest"]
    historical = checked(
        client, "GET", endpoint + f"/versions/{original_version}/download"
    ).content
    assert historical == original
    saved_bytes = checked(
        client, "GET", endpoint + f"/versions/{saved['saved_version_id']}/download"
    ).content
    assert saved_bytes == current_bytes
    history = checked(client, "GET", endpoint + "/versions").json()
    assert [entry["number"] for entry in history["items"]] == [2, 1]
    checked(client, "POST", "/api/auth/logout")
    return {
        "source_sha": source,
        "status": "succeeded",
        "versions_verified": 2,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "saved_sha256": hashlib.sha256(current_bytes).hexdigest(),
    }


def main():
    mode, source, output = sys.argv[1:]
    assert mode in {"login", "smoke"} and re.fullmatch("[0-9a-f]{40}", source)
    origin = os.environ["FILLABLE_PUBLIC_ORIGIN"]
    assert re.fullmatch(r"http://[a-z0-9.-]+:3200", origin)
    with httpx.Client(
        base_url=origin, headers={"Origin": origin}, timeout=40, trust_env=False
    ) as client:
        if not login(
            client,
            os.environ["FILLABLE_INITIAL_LOGIN"],
            os.environ["FILLABLE_INITIAL_PASSWORD"],
        ):
            return 3
        if mode == "smoke":
            result = smoke(client, source, Path("/fixtures/docx/v1"))
            Path(output).write_text(json.dumps(result, sort_keys=True) + "\n")
        else:
            checked(client, "POST", "/api/auth/logout")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("public_release_smoke_failed", file=sys.stderr)
        raise SystemExit(1) from None
