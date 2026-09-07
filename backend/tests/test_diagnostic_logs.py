import asyncio
import logging
import socket
import threading
import time
import traceback

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from starlette.background import BackgroundTask
from starlette.responses import Response, StreamingResponse

from app.errors import SanitizedErrors, register_errors

PRIVATE = "synthetic-private-document-value-and-token"


@pytest.fixture
def server(caplog):
    caplog.set_level(logging.ERROR)
    app = FastAPI()
    register_errors(app)

    @app.get("/failure")
    def failure():
        raise RuntimeError(PRIVATE)

    @app.get("/stream")
    def stream():
        def chunks():
            yield b"partial"
            raise RuntimeError(PRIVATE)

        return StreamingResponse(chunks())

    @app.get("/background")
    def background():
        def failed():
            raise RuntimeError(PRIVATE)

        return Response("complete", background=BackgroundTask(failed))

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    runtime = uvicorn.Server(
        uvicorn.Config(app, access_log=False, log_config=None, lifespan="off")
    )
    thread = threading.Thread(
        target=runtime.run, kwargs={"sockets": [sock]}, daemon=True
    )
    thread.start()
    deadline = time.monotonic() + 5
    while not runtime.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert runtime.started
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", trust_env=False
        ) as client:
            yield client
    finally:
        runtime.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive()


def test_real_uvicorn_unknown_failure_never_logs_original_message_or_request(
    server, caplog
):
    response = server.get(f"/failure?token={PRIVATE}", headers={"Cookie": PRIVATE})
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": {"code": "internal_error", "parameters": {}}}
    assert "request_failed" in caplog.text
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("path", ["/stream", "/background"])
def test_real_uvicorn_late_failure_logs_only_sanitized_exception(server, caplog, path):
    if path == "/stream":
        with pytest.raises(httpx.RemoteProtocolError):
            server.get(path)
    else:
        response = server.get(path)
        assert response.text == "complete"
    deadline = time.monotonic() + 3
    while (
        "RuntimeError: request_failed" not in caplog.text
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert "RuntimeError: request_failed" in caplog.text
    assert PRIVATE not in caplog.text


def test_non_http_and_cancellation_keep_their_lifecycle_contract(caplog):
    async def downstream(scope, receive, send):
        if scope["type"] == "http":
            raise asyncio.CancelledError()
        await send({"type": "lifespan.startup.complete"})

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {}

    boundary = SanitizedErrors(downstream)
    asyncio.run(boundary({"type": "lifespan"}, receive, send))
    assert sent == [{"type": "lifespan.startup.complete"}]
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(boundary({"type": "http"}, receive, send))
    assert "request_failed" not in caplog.text


def test_fallback_transport_failure_has_no_original_exception_context():
    async def downstream(scope, receive, send):
        raise RuntimeError(PRIVATE)

    async def send(message):
        raise RuntimeError("transport_failed")

    async def receive():
        return {}

    with pytest.raises(RuntimeError, match="transport_failed") as failure:
        asyncio.run(SanitizedErrors(downstream)({"type": "http"}, receive, send))
    assert PRIVATE not in "".join(traceback.format_exception(failure.value))
