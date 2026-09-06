from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Fillable", docs_url=None, redoc_url=None)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/api/health", response_model=Health)
def health() -> Health:
    """Process health; dependency readiness is added with persistent services."""
    return Health(status="ok")
