from fastapi import APIRouter, Depends, Response

from app.accounts.routes import current_user
from app.accounts.schema import UserInfo
from app.storage.quotas import usage
from app.storage.schema import QuotaUsage

router = APIRouter(prefix="/api/storage")


@router.get("/usage", response_model=QuotaUsage)
def current_usage(
    response: Response, user: UserInfo = Depends(current_user)
) -> QuotaUsage:
    response.headers["Cache-Control"] = "no-store"
    return usage(user.id)
