"""Explicit isolated QA: the real dispatcher and forked RQ worker complete intent."""
import hashlib
import os
import time

import httpx

origin = os.environ["FILLABLE_PUBLIC_ORIGIN"]
with httpx.Client(base_url=origin, headers={"Origin": origin}, timeout=30) as client:
    response = client.get("/api/auth/session")
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    response = client.post("/api/auth/login", json={"email": "profile@example.test", "password": "Synthetic-browser-Їжак-2026"})
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    response = client.get("/api/documents", params={"kind": "template"})
    response.raise_for_status()
    saved = response.json()["items"][0]
    before = client.get("/api/storage/usage").json()["used_bytes"]
    endpoint = f"/api/documents/{saved['id']}/processing"
    response = client.get(endpoint)
    response.raise_for_status()
    identity = response.json()["id"]
    for _ in range(30):
        response = client.get(endpoint)
        response.raise_for_status()
        status = response.json()
        if status["status"] == "succeeded":
            break
        assert status["status"] in {"queued", "running"}
        time.sleep(1)
    else:
        raise RuntimeError("Processing did not finish within QA deadline")
    assert status["source_version_id"] == saved["current_version_id"]
    assert status["summary"]["supported_controls"] > 0
    fields = client.get(f"/api/documents/{saved['id']}/fields")
    fields.raise_for_status()
    assert fields.json()["status"] == "succeeded"
    snapshot = fields.json()["snapshot"]
    assert snapshot["source_version_id"] == saved["current_version_id"]
    assert len(snapshot["candidates"]) == 23
    assert len(snapshot["decisions"]) == 5
    assert client.post(endpoint).json()["id"] == identity
    download = client.get(f"/api/documents/{saved['id']}/download")
    download.raise_for_status()
    assert hashlib.sha256(download.content).hexdigest() == saved["digest"]
    assert client.get("/api/storage/usage").json()["used_bytes"] == before
    client.post("/api/auth/logout").raise_for_status()
print("PASS: durable discovery completed through dispatcher/worker; saved bytes and quota unchanged")
