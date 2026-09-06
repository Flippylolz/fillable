from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import SQLAlchemyError

from app.accounts.routes import current_user, mutation_session
from app.accounts.schema import UserInfo
from app.accounts.service import SessionState
from app.errors import AppError
from app.jobs import service
from app.jobs.schema import FieldsResult, ProcessingInfo

router = APIRouter(prefix="/api/documents")


@router.get("/{identity}/processing", response_model=ProcessingInfo)
def status(
    identity: UUID, response: Response, user: UserInfo = Depends(current_user)
) -> ProcessingInfo:
    response.headers["Cache-Control"] = "no-store"
    return service.status(user.id, identity)


@router.post("/{identity}/processing", response_model=ProcessingInfo)
def submit(
    identity: UUID, response: Response, state: SessionState = Depends(mutation_session)
) -> ProcessingInfo:
    try:
        result = service.submit(state, identity)
    except SQLAlchemyError:
        raise AppError(503, "dependencies_unavailable") from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{identity}/fields", response_model=FieldsResult)
def fields(
    identity: UUID, response: Response, user: UserInfo = Depends(current_user)
) -> FieldsResult:
    try:
        result = service.fields(user.id, identity)
    except (SQLAlchemyError, ValueError):
        raise AppError(503, "dependencies_unavailable") from None
    response.headers["Cache-Control"] = "no-store"
    return result
