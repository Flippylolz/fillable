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
    # The offending parameter's name and machine reason identify the field;
    # the submitted value itself is never echoed.
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "parameters": {"parameter": "count", "reason": "int_parsing"},
        }
    }
    assert "private input" not in response.text
    assert client.get("/application").json() == {
        "error": {
            "code": "dependencies_unavailable",
            "parameters": {"retry_seconds": 5},
        }
    }


def test_validation_errors_name_the_parameter_without_exposing_values():
    app = FastAPI()
    register_errors(app)

    class Body(BaseModel):
        model_config = {"extra": "forbid"}
        display_name: str
        nested: list[int] = []

    @app.post("/body")
    def body(data: Body):
        return data

    @app.get("/query")
    def query(kind: str):
        return kind

    client = TestClient(app, raise_server_exceptions=False)
    missing = client.get("/query")
    assert missing.status_code == 422
    assert missing.json()["error"]["parameters"] == {
        "parameter": "kind",
        "reason": "missing",
    }
    short = client.post(
        "/body", json={"display_name": " Ґанна ", "nested": [1, "x"]}
    )
    assert short.json()["error"]["parameters"] == {
        "parameter": "nested",
        "reason": "int_parsing",
    }
    hostile = "Ї" + "x" * 80 + "\n\t control"
    extra = client.post(
        "/body", json={"display_name": "Ґанна", hostile: "submitted value"}
    )
    assert extra.status_code == 422
    parameters = extra.json()["error"]["parameters"]
    assert parameters["reason"] == "extra_forbidden"
    assert len(parameters["parameter"]) <= 64
    assert parameters["parameter"].isprintable()
    assert "submitted value" not in extra.text
    unnamed = client.post(
        "/body",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert unnamed.status_code == 422
    assert unnamed.json()["error"]["parameters"] in (
        {},
        {"parameter": "body", "reason": "json_invalid"},
    )
