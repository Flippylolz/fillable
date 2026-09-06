import hmac
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response

from app.accounts import service
from app.accounts.schema import LoginInput, SessionInfo, UserInfo
from app.errors import AppError

router = APIRouter(prefix="/api/auth")
COOKIE = "fillable_session_v1"


def public_origin() -> str:
    value = os.environ["FILLABLE_PUBLIC_ORIGIN"]
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_public_origin")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    port = parsed.port
    suffix = (
        f":{port}"
        if port is not None and port != (443 if parsed.scheme == "https" else 80)
        else ""
    )
    return f"{parsed.scheme}://{host}{suffix}"


def cookie_token(request: Request) -> str | None:
    names = [
        part.strip().split("=", 1)[0]
        for part in request.headers.get("cookie", "").split(";")
    ]
    return request.cookies.get(COOKIE) if names.count(COOKIE) == 1 else None


def session_response(state: service.SessionState, response: Response) -> SessionInfo:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        COOKIE,
        state.token,
        httponly=True,
        secure=public_origin().startswith("https:"),
        samesite="strict",
        path="/",
        max_age=max(0, int((state.expires_at - service.now()).total_seconds())),
    )
    return SessionInfo(user=state.user, csrf_token=service.csrf_token(state.token))


def current_session(request: Request) -> service.SessionState:
    state = service.read_session(cookie_token(request))
    if state is None:
        raise AppError(401, "authentication_required")
    return state


def current_user(state: service.SessionState = Depends(current_session)) -> UserInfo:
    if state.user is None:
        raise AppError(401, "authentication_required")
    return state.user


def administrator(user: UserInfo = Depends(current_user)) -> UserInfo:
    return service.require_role(user, "admin")


def mutation_session(request: Request) -> service.SessionState:
    if request.headers.get("origin") != public_origin():
        raise AppError(403, "forbidden")
    state = current_session(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not hmac.compare_digest(
        supplied.encode(), service.csrf_token(state.token).encode()
    ):
        raise AppError(403, "forbidden")
    return state


@router.get("/session", response_model=SessionInfo)
def session(request: Request, response: Response) -> SessionInfo:
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise AppError(403, "forbidden")
    return session_response(service.bootstrap(cookie_token(request)), response)


@router.post("/login", response_model=SessionInfo)
def login(
    payload: LoginInput,
    response: Response,
    state: service.SessionState = Depends(mutation_session),
) -> SessionInfo:
    return session_response(
        service.login(state.token, payload.email, payload.password), response
    )


@router.post("/logout", response_model=SessionInfo)
def logout(
    response: Response, state: service.SessionState = Depends(mutation_session)
) -> SessionInfo:
    return session_response(service.logout(state.token), response)
