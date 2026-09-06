from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.accounts.profile import router as profile_router
from app.accounts.routes import router as authentication_router
from app.errors import AppError, ErrorEnvelope, register_errors
from app.infrastructure import dependencies_ready
from app.storage.routes import router as storage_router

app = FastAPI(
    title="Fillable",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    responses={
        status: {"model": ErrorEnvelope}
        for status in (400, 401, 403, 404, 405, 409, 422, 429, 500, 503)
    },
)
register_errors(app)
app.include_router(authentication_router)
app.include_router(profile_router)
app.include_router(storage_router)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/api/health", response_model=Health)
def health() -> Health:
    """Process health; dependency readiness is added with persistent services."""
    return Health(status="ok")


@app.get("/api/ready", response_model=Health)
def ready() -> Health:
    if not dependencies_ready():
        raise AppError(503, "dependencies_unavailable")
    return Health(status="ok")
