"""Serialize one editor per resource; never write files or consume quota."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, update

from app.accounts.profile import active_user
from app.accounts.schema import sessions
from app.accounts.service import IDLE_SECONDS, token_hash
from app.documents.lease_schema import LeaseInfo, leases
from app.documents.schema import resources
from app.documents.service import query
from app.errors import AppError
from app.infrastructure import database

LEASE_SECONDS = 60


def change(state, identity, payload):
    with database().begin() as connection:
        owner = active_user(connection, state)["id"]
        resource = (
            connection.execute(
                select(resources)
                .where(resources.c.id == identity, resources.c.owner_id == owner)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if resource is None or resource["state"] != "active":
            raise AppError(404, "not_found")
        row = (
            connection.execute(select(leases).where(leases.c.document_id == identity))
            .mappings()
            .one_or_none()
        )
        session_hash = token_hash(state.token)
        same = (
            row is not None
            and row["session_hash"] == session_hash
            and row["client_id"] == payload.client_id
        )
        generation = (
            same
            and row["lease_id"] == payload.lease_id
            and row["source_version_id"] == payload.source_version_id
        )
        if payload.action == "release":
            if generation:
                connection.execute(
                    delete(leases).where(leases.c.document_id == identity)
                )
            return LeaseInfo(
                status="released",
                source_version_id=payload.source_version_id,
                lease_id=payload.lease_id,
                expires_at=None,
                valid_for_seconds=0,
            )
        if resource["current_version_id"] != payload.source_version_id:
            raise AppError(409, "operation_conflict", {"reason": "revision"})
        if (
            connection.execute(query(owner).where(resources.c.id == identity)).first()
            is None
        ):
            raise AppError(404, "not_found")
        now = connection.execute(select(func.clock_timestamp())).scalar_one()
        live = (
            row is not None
            and row["expires_at"] > now
            and connection.execute(
                select(sessions.c.token_hash).where(
                    sessions.c.token_hash == row["session_hash"],
                    sessions.c.user_id == owner,
                    sessions.c.expires_at > now,
                    sessions.c.last_seen_at > now - timedelta(seconds=IDLE_SECONDS),
                )
            ).first()
            is not None
        )
        if payload.action == "renew" and (not live or not generation):
            raise AppError(409, "operation_conflict", {"reason": "lease_lost"})
        if payload.action == "acquire" and live and not same:
            raise AppError(409, "operation_conflict", {"reason": "lease_busy"})
        identity_token = (
            row["lease_id"]
            if live and same and row["source_version_id"] == payload.source_version_id
            else uuid4()
        )
        expires = now + timedelta(seconds=LEASE_SECONDS)
        values = dict(
            owner_id=owner,
            source_version_id=payload.source_version_id,
            session_hash=session_hash,
            client_id=payload.client_id,
            lease_id=identity_token,
            expires_at=expires,
        )
        if row is None:
            connection.execute(insert(leases).values(document_id=identity, **values))
        else:
            connection.execute(
                update(leases).where(leases.c.document_id == identity).values(**values)
            )
        return LeaseInfo(
            status="active",
            source_version_id=payload.source_version_id,
            lease_id=identity_token,
            expires_at=expires,
            valid_for_seconds=LEASE_SECONDS,
        )
