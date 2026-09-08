from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
)

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(254), unique=True, nullable=False),
    Column("display_name", String(120), nullable=False),
    Column("password_hash", String(512), nullable=False),
    Column("role", String(10), nullable=False, server_default="user"),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("ui_language", String(2), nullable=False, server_default="uk"),
    CheckConstraint("role IN ('user', 'admin')", name="users_role"),
    CheckConstraint("ui_language IN ('uk', 'en')", name="users_language"),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE")),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
)
login_attempts = Table(
    "login_attempts",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("count", Integer, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
)


class UserInfo(BaseModel):
    id: UUID
    login: str = Field(validation_alias=AliasChoices("login", "email"))
    display_name: str
    role: Literal["user", "admin"]
    ui_language: Literal["uk", "en"]


class AccountInput(BaseModel):
    login: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[\w.@+-]+$",
        validation_alias=AliasChoices("login", "email"),
    )
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["user", "admin"] = "user"
    ui_language: Literal["uk", "en"] = "uk"

    @field_validator("login", mode="before")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("invalid_login")
        return value.strip().casefold()

    @field_validator("display_name")
    @classmethod
    def display_name_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty_display_name")
        return value.strip()


class LoginInput(BaseModel):
    login: str = Field(
        min_length=1, max_length=254, validation_alias=AliasChoices("login", "email")
    )
    password: str = Field(min_length=1, max_length=1024)


class SessionInfo(BaseModel):
    user: UserInfo | None
    csrf_token: str
