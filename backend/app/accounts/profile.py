"""Owner-only profile edits with current-credential verification and session fencing."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, update

from app.accounts import service
from app.accounts.routes import mutation_session, session_response
from app.accounts.schema import (
    AccountInput,
    SessionInfo,
    UserInfo,
    login_attempts,
    sessions,
    users,
)
from app.errors import AppError
from app.infrastructure import database

router = APIRouter(prefix="/api/profile")


class NameInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def present(cls, value):
        return AccountInput.display_name_present(value)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class LanguageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ui_language: Literal["uk", "en"]


def active_user(connection, state):
    if state.user is None:
        raise AppError(401, "authentication_required")
    user = (
        connection.execute(
            select(users)
            .where(
                users.c.id == state.user.id,
                users.c.active.is_(True),
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    session = (
        connection.execute(
            select(sessions)
            .where(
                sessions.c.token_hash == service.token_hash(state.token),
                sessions.c.user_id == state.user.id,
                sessions.c.expires_at > service.now(),
                sessions.c.last_seen_at
                > service.now() - timedelta(seconds=service.IDLE_SECONDS),
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if user is None or session is None:
        raise AppError(401, "authentication_required")
    return user


def rename(state, payload):
    return update_preference(state, payload.model_dump())


def update_preference(state, values):
    with database().begin() as connection:
        user = active_user(connection, state)
        connection.execute(
            update(users).where(users.c.id == user["id"]).values(**values)
        )
        updated = UserInfo.model_validate({**dict(user), **values})
        return service.SessionState(state.token, updated, state.expires_at)


def change_password(state, payload):
    if state.user is None:
        raise AppError(401, "authentication_required")
    key = service.attempt_key(f"password-change:{state.user.id}")
    result, limited = None, False
    with database().begin() as connection:
        bucket = service.lock_attempt(connection, key)
        user = active_user(connection, state)
        if bucket["count"] >= 5:
            limited = True
        else:
            connection.execute(
                update(login_attempts)
                .where(login_attempts.c.key == key)
                .values(
                    count=login_attempts.c.count + 1,
                )
            )
            if service.verify_password(user["password_hash"], payload.current_password):
                hashed = service.hash_password(payload.new_password)
                connection.execute(
                    update(users)
                    .where(users.c.id == user["id"])
                    .values(password_hash=hashed)
                )
                connection.execute(
                    delete(sessions).where(sessions.c.user_id == user["id"])
                )
                connection.execute(
                    delete(login_attempts).where(login_attempts.c.key == key)
                )
                result = service.issue(connection, UserInfo.model_validate(dict(user)))
    if limited:
        raise AppError(429, "rate_limited")
    if result is None:
        raise AppError(400, "current_password_invalid")
    return result


@router.patch("", response_model=SessionInfo)
def update_name(
    payload: NameInput,
    response: Response,
    state: service.SessionState = Depends(mutation_session),
) -> SessionInfo:
    return session_response(rename(state, payload), response)


@router.post("/password", response_model=SessionInfo)
def update_password(
    payload: PasswordInput,
    response: Response,
    state: service.SessionState = Depends(mutation_session),
) -> SessionInfo:
    return session_response(change_password(state, payload), response)


@router.patch("/language", response_model=SessionInfo)
def update_language(
    payload: LanguageInput,
    response: Response,
    state: service.SessionState = Depends(mutation_session),
) -> SessionInfo:
    return session_response(update_preference(state, payload.model_dump()), response)
