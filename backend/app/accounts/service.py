"""Account and session transactions; no credentials or raw tokens are logged."""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from threading import BoundedSemaphore
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.accounts.schema import AccountInput, UserInfo, login_attempts, sessions, users
from app.errors import AppError
from app.infrastructure import database
from app.storage.schema import accounts as storage_accounts

PASSWORDS = PasswordHasher()
PASSWORD_SLOTS = BoundedSemaphore(2)
AUTH_SECONDS = 12 * 60 * 60
ANONYMOUS_SECONDS = 15 * 60
IDLE_SECONDS = 30 * 60


def now() -> datetime:
    return datetime.now(UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(("session:" + token).encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hashlib.sha256(("csrf:" + token).encode()).hexdigest()


def attempt_key(email: str) -> str:
    return hashlib.sha256(email.strip().casefold().encode()).hexdigest()


def hash_password(password: str) -> str:
    # Bound Argon2 memory across simultaneous requests in this API process.
    with PASSWORD_SLOTS:
        return PASSWORDS.hash(password)


def validate_password(password: str) -> None:
    if not 10 <= len(password) <= 1024:
        raise ValueError("invalid_password")


def provision(account: AccountInput, password: str) -> UserInfo:
    validate_password(password)
    values = {**account.model_dump(), "id": uuid4()}
    # Preserve existing unique identifiers and account references in the legacy column.
    values["email"] = values.pop("login")
    try:
        with database().begin() as connection:
            connection.execute(
                insert(users).values(
                    **values,
                    password_hash=hash_password(password),
                    active=True,
                )
            )
            connection.execute(insert(storage_accounts).values(user_id=values["id"]))
    except IntegrityError as error:
        raise AppError(409, "account_exists") from error
    return UserInfo.model_validate(values)


def reset_password(email: str, password: str) -> None:
    validate_password(password)
    hashed = hash_password(password)
    with database().begin() as connection:
        lock_attempt(connection, attempt_key(email))
        user_id = connection.execute(
            select(users.c.id)
            .where(users.c.email == email.strip().casefold())
            .with_for_update()
        ).scalar()
        if user_id is None:
            raise AppError(404, "not_found")
        connection.execute(
            update(users).where(users.c.id == user_id).values(password_hash=hashed)
        )
        connection.execute(delete(sessions).where(sessions.c.user_id == user_id))
        connection.execute(
            delete(login_attempts).where(login_attempts.c.key == attempt_key(email))
        )


@lru_cache
def dummy_hash() -> str:
    return hash_password(secrets.token_hex(32))


def verify_password(hashed: str, password: str) -> bool:
    try:
        with PASSWORD_SLOTS:
            return PASSWORDS.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


@dataclass
class SessionState:
    token: str
    user: UserInfo | None
    expires_at: datetime


def issue(connection: Connection, user: UserInfo | None) -> SessionState:
    token = secrets.token_hex(32)
    expires = now() + timedelta(seconds=AUTH_SECONDS if user else ANONYMOUS_SECONDS)
    connection.execute(
        insert(sessions).values(
            token_hash=token_hash(token),
            user_id=user.id if user else None,
            expires_at=expires,
            last_seen_at=now(),
        )
    )
    return SessionState(token, user, expires)


def read_session(token: str | None) -> SessionState | None:
    if token is None or re.fullmatch(r"[0-9a-f]{64}", token) is None:
        return None
    with database().begin() as connection:
        row = (
            connection.execute(
                select(sessions)
                .where(sessions.c.token_hash == token_hash(token))
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        user = None
        if row["user_id"] is not None:
            account = (
                connection.execute(
                    select(users).where(
                        users.c.id == row["user_id"], users.c.active.is_(True)
                    )
                )
                .mappings()
                .first()
            )
            if account is not None:
                user = UserInfo.model_validate(dict(account))
        if (
            row["expires_at"] <= now()
            or row["last_seen_at"] + timedelta(seconds=IDLE_SECONDS) <= now()
            or (row["user_id"] is not None and user is None)
        ):
            connection.execute(
                delete(sessions).where(sessions.c.token_hash == row["token_hash"])
            )
            return None
        connection.execute(
            update(sessions)
            .where(sessions.c.token_hash == row["token_hash"])
            .values(last_seen_at=now())
        )
        return SessionState(token, user, row["expires_at"])


def bootstrap(token: str | None) -> SessionState:
    existing = read_session(token)
    if existing is not None:
        return existing
    with database().begin() as connection:
        connection.execute(delete(sessions).where(sessions.c.expires_at <= now()))
        return issue(connection, None)


def lock_attempt(connection, key):
    connection.execute(
        delete(login_attempts).where(login_attempts.c.expires_at <= now())
    )
    connection.execute(
        pg_insert(login_attempts)
        .values(
            key=key,
            count=0,
            expires_at=now() + timedelta(minutes=15),
        )
        .on_conflict_do_nothing()
    )
    return (
        connection.execute(
            select(login_attempts)
            .where(
                login_attempts.c.key == key,
            )
            .with_for_update()
        )
        .mappings()
        .one()
    )


def login(token: str, email: str, password: str) -> SessionState:
    email = email.strip().casefold()
    key = attempt_key(email)
    result = None
    limited = False
    with database().begin() as connection:
        bucket = lock_attempt(connection, key)
        if bucket["count"] >= 5:
            limited = True
        else:
            connection.execute(
                update(login_attempts)
                .where(login_attempts.c.key == key)
                .values(count=login_attempts.c.count + 1)
            )
            account = (
                connection.execute(
                    select(users).where(users.c.email == email).with_for_update()
                )
                .mappings()
                .first()
            )
            hashed = account["password_hash"] if account else dummy_hash()
            valid = verify_password(hashed, password)
            if valid and account is not None and account["active"]:
                previous = connection.execute(
                    delete(sessions)
                    .where(
                        sessions.c.token_hash == token_hash(token),
                        sessions.c.expires_at > now(),
                    )
                    .returning(sessions.c.token_hash)
                ).scalar()
                if previous is None:
                    raise AppError(403, "forbidden")
                if PASSWORDS.check_needs_rehash(hashed):
                    connection.execute(
                        update(users)
                        .where(users.c.id == account["id"])
                        .values(password_hash=hash_password(password))
                    )
                connection.execute(
                    delete(login_attempts).where(login_attempts.c.key == key)
                )
                result = issue(connection, UserInfo.model_validate(dict(account)))
    # Failed attempts must commit before their error response is raised.
    if limited:
        raise AppError(429, "rate_limited")
    if result is None:
        raise AppError(401, "invalid_credentials")
    return result


def logout(token: str) -> SessionState:
    with database().begin() as connection:
        connection.execute(
            delete(sessions).where(sessions.c.token_hash == token_hash(token))
        )
        return issue(connection, None)


def require_role(user: UserInfo, role: str) -> UserInfo:
    if role == "admin" and user.role != "admin":
        raise AppError(403, "forbidden")
    return user
