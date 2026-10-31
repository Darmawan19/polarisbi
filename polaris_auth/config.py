"""Pengaturan modul login. Semua bisa diubah lewat environment variable (prefix POLARIS_).

Dibaca ulang setiap dipanggil, jadi perubahan env (mis. saat tes) langsung berlaku.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_path: Path
    cookie_name: str
    cookie_secure: bool
    cookie_samesite: str          # "lax" | "strict" | "none"
    session_idle_seconds: int     # logout otomatis bila tidak ada aktivitas
    session_max_seconds: int      # batas mutlak umur sesi
    max_failed: int               # salah password berturut-turut sebelum akun dikunci
    lock_seconds: int             # lama akun dikunci
    ip_max_failed: int            # batas kegagalan per alamat IP dalam satu jendela
    trust_proxy: bool             # percaya header X-Forwarded-For (hanya bila di belakang reverse proxy)
    protected_prefixes: tuple[str, ...]
    bootstrap_user: str | None
    bootstrap_password: str | None
    bootstrap_name: str | None


def get_settings() -> Settings:
    default_db = Path(__file__).resolve().parent.parent / "data" / "polaris_auth.db"
    prefixes = tuple(
        p.strip().rstrip("/") or "/"
        for p in os.environ.get("POLARIS_PROTECTED_PREFIXES", "/api").split(",")
        if p.strip()
    )
    return Settings(
        db_path=Path(os.environ.get("POLARIS_AUTH_DB", str(default_db))),
        cookie_name=os.environ.get("POLARIS_COOKIE_NAME", "polarisbi_session"),
        cookie_secure=_bool("POLARIS_COOKIE_SECURE", False),
        cookie_samesite=os.environ.get("POLARIS_COOKIE_SAMESITE", "lax").lower(),
        session_idle_seconds=_int("POLARIS_SESSION_IDLE_MIN", 60) * 60,
        session_max_seconds=_int("POLARIS_SESSION_MAX_HOURS", 12) * 3600,
        max_failed=_int("POLARIS_MAX_FAILED", 5),
        lock_seconds=_int("POLARIS_LOCK_MIN", 15) * 60,
        ip_max_failed=_int("POLARIS_IP_MAX_FAILED", 30),
        trust_proxy=_bool("POLARIS_TRUST_PROXY", False),
        protected_prefixes=prefixes,
        bootstrap_user=os.environ.get("POLARIS_BOOTSTRAP_ADMIN_USER") or None,
        bootstrap_password=os.environ.get("POLARIS_BOOTSTRAP_ADMIN_PASSWORD") or None,
        bootstrap_name=os.environ.get("POLARIS_BOOTSTRAP_ADMIN_NAME") or None,
    )
