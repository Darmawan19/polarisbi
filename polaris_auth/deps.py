"""Dependency FastAPI + penjaga CSRF."""
from __future__ import annotations

from fastapi import Depends, Request

from . import service
from .config import get_settings
from .errors import AuthError

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "polarisbi"
_SAFE = {"GET", "HEAD", "OPTIONS"}


def client_ip(request_or_scope, headers=None) -> str | None:
    s = get_settings()
    if hasattr(request_or_scope, "headers"):
        headers, client = request_or_scope.headers, request_or_scope.client
    else:  # ASGI scope
        client = request_or_scope.get("client")
    if s.trust_proxy and headers is not None:
        fwd = headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return client[0] if client else None


def check_csrf(method: str, headers) -> None:
    """Permintaan yang mengubah data harus membawa header kustom.

    Header kustom memaksa browser melakukan preflight CORS, yang hanya lolos dari origin
    yang kita izinkan, sehingga situs lain tidak bisa memicu aksi atas nama pengguna.
    """
    if method.upper() not in _SAFE and headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise AuthError(403, "csrf", "Header keamanan tidak ada.")


def csrf_guard(request: Request) -> None:
    check_csrf(request.method, request.headers)


def _cookie_user(request: Request) -> dict | None:
    cached = getattr(request.state, "user", None)
    if cached is not None:
        return cached
    token = request.cookies.get(get_settings().cookie_name)
    user = service.validate_session(token)
    if user:
        request.state.user = user
    return user


def require_user_allow_pending(request: Request) -> dict:
    user = _cookie_user(request)
    if not user:
        raise AuthError(401, "not_authenticated", "Silakan login.")
    return user


def require_user(request: Request) -> dict:
    user = require_user_allow_pending(request)
    if user["must_change_password"]:
        raise AuthError(403, "password_change_required", "Ganti password terlebih dahulu.")
    return user


def require_role(*roles: str):
    def dep(user: dict = Depends(require_user)) -> dict:
        if user["role"] not in roles:
            raise AuthError(403, "forbidden", "Peran Anda tidak boleh mengakses ini.")
        return user
    return dep


require_admin = require_role("admin")
