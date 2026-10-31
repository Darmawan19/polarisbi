from __future__ import annotations

from fastapi import HTTPException


class AuthError(HTTPException):
    """Error dengan kode mesin (`detail.code`) supaya frontend bisa menerjemahkannya."""

    def __init__(self, status_code: int, code: str, message: str = "", headers: dict | None = None, **extra):
        super().__init__(status_code=status_code, detail={"code": code, "message": message or code, **extra}, headers=headers)
        self.code = code
