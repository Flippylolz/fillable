from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import AppError, register_errors


def test_errors_never_echo_internal_messages_or_submitted_values():
    app = FastAPI()
    register_errors(app)

    class Input(BaseModel):
        count: int

    @app.post("/validate")
    def validate(data: Input):
        return data

    @app.get("/http")
    def http():
        raise HTTPException(409, "private database information")

    @app.get("/application")
    def application():
        raise AppError(503, "dependencies_unavailable", {"retry_seconds": 5})

    @app.get("/unexpected")
    def unexpected():
        raise RuntimeError("private document value")

    client = TestClient(app, raise_server_exceptions=False)
    for path, status, code in [
        ("/missing", 404, "not_found"),
        ("/http", 409, "invalid_request"),
        ("/unexpected", 500, "internal_error"),
    ]:
        response = client.get(path)
        assert response.status_code == status
        assert response.json() == {"error": {"code": code, "parameters": {}}}
    assert client.post("/http").json()["error"]["code"] == "method_not_allowed"
    response = client.post("/validate", json={"count": "private input"})
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "invalid_request", "parameters": {}}}
    assert client.get("/application").json() == {
        "error": {
            "code": "dependencies_unavailable",
            "parameters": {"retry_seconds": 5},
        }
    }
