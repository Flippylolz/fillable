from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.infrastructure import dependencies_ready

app = FastAPI(title="Fillable", docs_url=None, redoc_url=None)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/api/health", response_model=Health)
def health() -> Health:
    """Process health; dependency readiness is added with persistent services."""
    return Health(status="ok")


@app.get("/api/ready", response_model=Health)
def ready() -> Health:
    if not dependencies_ready():
        raise HTTPException(503, detail={"code": "dependencies_unavailable"})
    return Health(status="ok")
