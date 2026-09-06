import base64
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.documents import prototype
from app.main import app


def test_proof_routes_are_opt_in_and_roundtrip_in_memory():
    production = TestClient(app)
    assert production.get("/api/prototype").status_code == 404
    client = TestClient(prototype.app)
    initial = client.get("/api/prototype").json()
    response = client.post("/api/prototype/export", json=initial)
    assert response.status_code == 200
    assert response.content == base64.b64decode(initial["source"])
    assert (
        client.post("/api/prototype/reopen", content=response.content).json() == initial
    )
    for payload in ({}, {"source": "%%%"}):
        assert client.post("/api/prototype/export", json=payload).status_code == 400
    assert client.post("/api/prototype/export", content="{broken").status_code == 400
    assert client.post("/api/prototype/reopen", content=b"invalid").status_code == 400
    with patch.object(prototype, "LIMIT", 2):
        assert client.post("/api/prototype/reopen", content=b"large").status_code == 400
