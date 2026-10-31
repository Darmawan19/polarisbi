"""Endpoint /auth/*."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from . import service
from .config import get_settings
from .deps import client_ip, csrf_guard, require_admin, require_user_allow_pending

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(csrf_guard)])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class CreateUserIn(BaseModel):
    username: str
    display_name: str | None = None
    role: str = "analyst"
    password: str | None = None  # kosong -> dibuatkan password sementara


class UpdateUserIn(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


def _out(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "session"}


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.cookie_name, value=token, max_age=s.session_max_seconds, path="/",
        httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite,
    )


def _clear_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(key=s.cookie_name, path="/", httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    user, token = service.authenticate(
        body.username, body.password, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
    )
    _set_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return {"user": _out(user)}


@router.post("/logout")
def logout(request: Request, response: Response):
    service.revoke_session(request.cookies.get(get_settings().cookie_name), ip=client_ip(request))
    _clear_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(response: Response, user: dict = Depends(require_user_allow_pending)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": _out(user)}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, user: dict = Depends(require_user_allow_pending)):
    service.change_password(user, body.current_password, body.new_password, ip=client_ip(request))
    return {"ok": True}


# ---- khusus admin ----

@router.get("/users")
def users(_: dict = Depends(require_admin)):
    return {"users": service.list_users()}


@router.post("/users", status_code=201)
def create_user(body: CreateUserIn, request: Request, admin: dict = Depends(require_admin)):
    from .security import generate_temp_password
    temp = None if body.password else generate_temp_password()
    user = service.create_user(
        body.username, body.password or temp, body.role, display_name=body.display_name,
        must_change=True, actor=admin["username"],
    )
    return {"user": user, "temporary_password": temp}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UpdateUserIn, request: Request, admin: dict = Depends(require_admin)):
    user = service.update_user(
        user_id, actor=admin, display_name=body.display_name, role=body.role,
        is_active=body.is_active, ip=client_ip(request),
    )
    return {"user": user}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, admin: dict = Depends(require_admin)):
    user, temp = service.reset_password(user_id, actor=admin["username"], ip=client_ip(request))
    return {"user": user, "temporary_password": temp}


@router.get("/audit")
def audit(limit: int = 100, offset: int = 0, _: dict = Depends(require_admin)):
    return {"entries": service.audit_entries(limit, offset)}
