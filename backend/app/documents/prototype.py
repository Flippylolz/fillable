"""Explicit opt-in synthetic editor proof; never mounted by the production app."""

import base64
import binascii
import json
from pathlib import Path

from fastapi import FastAPI, Request, Response

from app.documents.export import DocxExport
from app.documents.package import DocxPackage, InvalidDocument
from app.errors import AppError, register_errors
from app.main import app as production_app

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.router.routes.extend(production_app.router.routes)
register_errors(app)
LIMIT = 24 * 1024 * 1024


def snapshot(data: bytes) -> dict:
    package = DocxPackage(data)
    return {
        "source": base64.b64encode(data).decode("ascii"),
        "digest": package.digest,
        "model": package.model,
    }


async def bounded_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > LIMIT:
            raise AppError(400, "invalid_request")
    return bytes(body)


@app.get("/api/prototype")
def corpus() -> dict:
    return snapshot(Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes())


@app.post("/api/prototype/reopen")
async def reopen(request: Request) -> dict:
    try:
        return snapshot(await bounded_body(request))
    except InvalidDocument as error:
        raise AppError(400, "invalid_request") from error


@app.post("/api/prototype/export")
async def export(request: Request) -> Response:
    try:
        payload = json.loads(await bounded_body(request))
        source = base64.b64decode(payload["source"], validate=True)
        package = DocxPackage(source)
        data = DocxExport(package).render(payload["model"], payload["digest"])
    except (ValueError, KeyError, TypeError, binascii.Error) as error:
        raise AppError(400, "invalid_request") from error
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="editor-proof.docx"'},
    )
