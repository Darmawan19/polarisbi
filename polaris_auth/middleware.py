"""Penjaga otomatis untuk semua rute berawalan /api (atau prefix lain di POLARIS_PROTECTED_PREFIXES).

ASGI murni (bukan BaseHTTPMiddleware) agar streaming SSE tidak tertahan/ter-buffer.
"""
from __future__ import annotations

import anyio
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import service
from .config import get_settings
from .deps import check_csrf
from .errors import AuthError


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    def _protected(self, path: str) -> bool:
        for p in get_settings().protected_prefixes:
            if p == "/" or path == p or path.startswith(p + "/"):
                return True
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or not self._protected(scope["path"]):
            return await self.app(scope, receive, send)
        try:
            token = Request(scope).cookies.get(get_settings().cookie_name)
            user = await anyio.to_thread.run_sync(service.validate_session, token)
            if user is None:
                raise AuthError(401, "not_authenticated", "Silakan login.")
            if user["must_change_password"]:
                raise AuthError(403, "password_change_required", "Ganti password terlebih dahulu.")
            check_csrf(scope["method"], Headers(scope=scope))
        except AuthError as e:
            resp = JSONResponse({"detail": e.detail}, status_code=e.status_code, headers=e.headers)
            return await resp(scope, receive, send)
        scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)
