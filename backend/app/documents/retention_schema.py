"""Explicit operator history policy; all retained revisions are kept by default."""

from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, CheckConstraint, Column, Integer, Table

from app.accounts.schema import metadata

KeepLatest = Annotated[int, Field(strict=True, ge=1, le=10000)]
settings = Table(
    "history_retention_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("keep_latest", Integer),
    Column("revision", BigInteger, nullable=False, server_default="0"),
    CheckConstraint("id = 1", name="history_retention_singleton"),
    CheckConstraint(
        "keep_latest IS NULL OR keep_latest BETWEEN 1 AND 10000",
        name="history_retention_bounds",
    ),
    CheckConstraint("revision >= 0", name="history_retention_revision"),
)


class RetentionInfo(BaseModel):
    keep_latest: KeepLatest | None
    revision: int
