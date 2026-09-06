import asyncio
import base64
from threading import BoundedSemaphore
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.accounts.routes import current_user, mutation_session
from app.accounts.schema import UserInfo
from app.accounts.service import SessionState
from app.documents import deletion, service
from app.documents.package import ARCHIVE_BYTES, InvalidDocument
from app.documents.schema import (
    ContentInfo,
    DeletionResult,
    ResourceInfo,
    ResourceList,
    UploadMetadata,
)
from app.errors import AppError, ErrorCode
from app.storage.service import StorageError

router = APIRouter(prefix="/api/documents")
UPLOAD_SLOTS = BoundedSemaphore(2)
DOWNLOAD_SLOTS = BoundedSemaphore(2)
BODY_SECONDS = 30
MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def parse_metadata(value):
    try:
        return UploadMetadata.model_validate_json(
            base64.b64decode(value, validate=True)
        )
    except ValueError:
        raise AppError(422, "invalid_request") from None


async def read_body(request):
    if request.headers.get("content-type", "").split(";", 1)[0] not in {
        MIME,
        "application/octet-stream",
    }:
        raise AppError(415, "unsupported_document")
    declared = request.headers.get("content-length")
    if declared is not None and (
        not declared.isascii() or not declared.isdecimal() or len(declared) > 10
    ):
        raise AppError(400, "invalid_request")
    if declared is not None and int(declared) > ARCHIVE_BYTES:
        raise AppError(413, "file_too_large")
    body = bytearray()
    try:
        async with asyncio.timeout(BODY_SECONDS):
            async for chunk in request.stream():
                if len(body) + len(chunk) > ARCHIVE_BYTES:
                    raise AppError(413, "file_too_large")
                body.extend(chunk)
    except TimeoutError:
        raise AppError(408, "upload_timeout") from None
    if declared is not None and len(body) != int(declared):
        raise AppError(400, "invalid_request")
    return bytes(body)


@router.post(
    "",
    response_model=ResourceInfo,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {MIME: {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload(
    request: Request,
    response: Response,
    metadata: Annotated[
        str,
        Header(
            alias="X-Upload-Metadata",
            max_length=4096,
            description="Base64-encoded UTF-8 JSON with kind, filename and title.",
        ),
    ],
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
    state: SessionState = Depends(mutation_session),
) -> ResourceInfo:
    if state.user is None:
        raise AppError(401, "authentication_required")
    if not UPLOAD_SLOTS.acquire(blocking=False):
        raise AppError(429, "upload_busy")
    try:
        payload = parse_metadata(metadata)
        data = await read_body(request)
        result = await run_in_threadpool(
            service.upload, state, payload, data, idempotency_key
        )
    except InvalidDocument as error:
        code: ErrorCode = (
            "unsupported_document"
            if str(error) == "unsupported_document"
            else "document_limit"
            if "limit" in str(error)
            else "invalid_document"
        )
        raise AppError(422, code) from None
    except StorageError as error:
        failures: dict[str, tuple[int, ErrorCode]] = {
            "quota_exceeded": (409, "quota_exceeded"),
            "file_too_large": (413, "file_too_large"),
            "idempotency_conflict": (409, "operation_conflict"),
            "operation_in_progress": (409, "operation_in_progress"),
            "operation_aborted": (409, "operation_aborted"),
            "invalid_request": (422, "invalid_request"),
        }
        status, code = failures.get(error.code, (503, "storage_unavailable"))
        raise AppError(status, code) from None
    except SQLAlchemyError:
        raise AppError(503, "storage_unavailable") from None
    finally:
        UPLOAD_SLOTS.release()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("", response_model=ResourceList)
def listing(
    response: Response,
    kind: Literal["template", "document"],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: UUID | None = None,
    user: UserInfo = Depends(current_user),
) -> ResourceList:
    response.headers["Cache-Control"] = "no-store"
    return service.listing(user.id, kind, limit, cursor)


@router.get("/{identity}", response_model=ResourceInfo)
def detail(
    identity: UUID, response: Response, user: UserInfo = Depends(current_user)
) -> ResourceInfo:
    response.headers["Cache-Control"] = "no-store"
    return service.detail(user.id, identity)


@router.delete("/{identity}", response_model=DeletionResult)
def remove(
    identity: UUID, response: Response, state: SessionState = Depends(mutation_session)
) -> DeletionResult:
    try:
        result = deletion.remove(state, identity)
    except SQLAlchemyError:
        raise AppError(503, "storage_unavailable") from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/{identity}/download",
    response_class=Response,
    responses={
        200: {"content": {MIME: {"schema": {"type": "string", "format": "binary"}}}}
    },
)
def download(identity: UUID, user: UserInfo = Depends(current_user)) -> Response:
    if not DOWNLOAD_SLOTS.acquire(blocking=False):
        raise AppError(409, "operation_in_progress")
    try:
        resource, data = service.download(user.id, identity)
        return Response(
            data,
            media_type=MIME,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Fillable-Version": str(resource.current_version_id),
                "Content-Disposition": 'attachment; filename="document.docx"; '
                "filename*=UTF-8''" + quote(resource.original_filename, safe=""),
            },
        )
    except StorageError as error:
        if error.code == "not_found":
            raise AppError(404, "not_found") from None
        if error.code == "operation_in_progress":
            raise AppError(409, "operation_in_progress") from None
        raise AppError(503, "storage_unavailable") from None
    except SQLAlchemyError:
        raise AppError(503, "storage_unavailable") from None
    finally:
        DOWNLOAD_SLOTS.release()


@router.get("/{identity}/content", response_model=ContentInfo)
def content(
    identity: UUID, response: Response, user: UserInfo = Depends(current_user)
) -> ContentInfo:
    if not DOWNLOAD_SLOTS.acquire(blocking=False):
        raise AppError(409, "operation_in_progress")
    try:
        result = service.content(user.id, identity)
    except StorageError as error:
        if error.code == "not_found":
            raise AppError(404, "not_found") from None
        if error.code == "operation_in_progress":
            raise AppError(409, "operation_in_progress") from None
        raise AppError(503, "storage_unavailable") from None
    except SQLAlchemyError:
        raise AppError(503, "storage_unavailable") from None
    finally:
        DOWNLOAD_SLOTS.release()
    response.headers["Cache-Control"] = "no-store"
    return result
