"""Logika inti: pengguna, login, sesi, kunci akun, audit."""
from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any

from . import db as dbm
from .config import Settings, get_settings
from .errors import AuthError
from .security import (
    DUMMY_HASH, generate_temp_password, hash_password, hash_token, new_token,
    password_problem, validate_username, verify_password,
)

log = logging.getLogger("polaris_auth")
ROLES = ("admin", "analyst", "viewer")
_TOUCH_EVERY = 30  # detik; kurangi tulis ke DB


def now() -> int:  # dipisah supaya mudah dimanipulasi di tes
    return int(time.time())


def public_user(row: sqlite3.Row | dict) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "must_change_password": bool(row["must_change_password"]),
        "is_active": bool(row["is_active"]),
    }


def audit(conn, event: str, *, user_id=None, username=None, ip=None, detail=None) -> None:
    conn.execute(
        "INSERT INTO audit_log(ts,event,user_id,username,ip,detail) VALUES (?,?,?,?,?,?)",
        (now(), event, user_id, username, ip, (detail or None) and str(detail)[:500]),
    )


def init_auth(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    dbm.init_schema(s.db_path)
    if s.bootstrap_user and s.bootstrap_password:
        with dbm.session(s.db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n == 0:
            create_user(
                s.bootstrap_user, s.bootstrap_password, "admin",
                display_name=s.bootstrap_name or s.bootstrap_user, must_change=True, settings=s, actor="bootstrap",
            )
            log.warning("Admin awal '%s' dibuat dari environment; wajib ganti password saat login pertama.", s.bootstrap_user)


# ---------- pengguna ----------

def create_user(username: str, password: str, role: str, *, display_name: str | None = None,
                must_change: bool = False, settings: Settings | None = None, actor: str | None = None) -> dict:
    s = settings or get_settings()
    username = (username or "").strip()
    if not validate_username(username):
        raise AuthError(422, "invalid_username", "Username 3-50 karakter: huruf, angka, titik, garis bawah, @ atau tanda minus.")
    if role not in ROLES:
        raise AuthError(422, "invalid_role", f"Peran harus salah satu dari {', '.join(ROLES)}.")
    problem = password_problem(password, username)
    if problem:
        raise AuthError(422, "weak_password", "Password belum memenuhi aturan.", reason=problem)
    ph = hash_password(password)
    t = now()
    with dbm.session(s.db_path) as conn:
        try:
            with dbm.tx(conn):
                cur = conn.execute(
                    "INSERT INTO users(username,display_name,password_hash,role,must_change_password,created_at,password_changed_at)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (username, (display_name or username).strip()[:100], ph, role, 1 if must_change else 0, t, t),
                )
                uid = cur.lastrowid
                audit(conn, "user_created", user_id=uid, username=username, detail=f"role={role} by={actor or '-'}")
        except sqlite3.IntegrityError:
            raise AuthError(409, "user_exists", "Username sudah dipakai.")
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return public_user(row)


def list_users(settings: Settings | None = None) -> list[dict]:
    s = settings or get_settings()
    with dbm.session(s.db_path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    out = []
    for r in rows:
        d = public_user(r)
        d["last_login_at"] = r["last_login_at"]
        d["created_at"] = r["created_at"]
        out.append(d)
    return out


def _active_admin_count(conn, excluding_id: int | None = None) -> int:
    q = "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1"
    args: tuple = ()
    if excluding_id is not None:
        q += " AND id<>?"
        args = (excluding_id,)
    return conn.execute(q, args).fetchone()[0]


def update_user(user_id: int, *, actor: dict, display_name=None, role=None, is_active=None,
                settings: Settings | None = None, ip: str | None = None) -> dict:
    s = settings or get_settings()
    if role is not None and role not in ROLES:
        raise AuthError(422, "invalid_role", f"Peran harus salah satu dari {', '.join(ROLES)}.")
    with dbm.session(s.db_path) as conn:
        with dbm.tx(conn):
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                raise AuthError(404, "not_found", "Pengguna tidak ditemukan.")
            new_role = role if role is not None else row["role"]
            new_active = (1 if is_active else 0) if is_active is not None else row["is_active"]
            losing_admin = row["role"] == "admin" and row["is_active"] and (new_role != "admin" or not new_active)
            if losing_admin:
                if row["id"] == actor["id"]:
                    raise AuthError(400, "cannot_demote_self", "Anda tidak bisa menurunkan atau menonaktifkan akun Anda sendiri.")
                if _active_admin_count(conn, excluding_id=row["id"]) == 0:
                    raise AuthError(400, "last_admin", "Harus tersisa minimal satu admin aktif.")
            conn.execute(
                "UPDATE users SET display_name=?, role=?, is_active=? WHERE id=?",
                ((display_name or row["display_name"]).strip()[:100], new_role, new_active, user_id),
            )
            if not new_active:
                conn.execute("UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now(), user_id))
            audit(conn, "user_updated", user_id=user_id, username=row["username"], ip=ip,
                  detail=f"by={actor['username']} role={new_role} active={new_active}")
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return public_user(row)


def reset_password(user_id: int, *, actor: str, new_password: str | None = None,
                   settings: Settings | None = None, ip: str | None = None) -> tuple[dict, str]:
    s = settings or get_settings()
    pw = new_password or generate_temp_password()
    with dbm.session(s.db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise AuthError(404, "not_found", "Pengguna tidak ditemukan.")
        problem = password_problem(pw, row["username"])
        if problem:
            raise AuthError(422, "weak_password", "Password belum memenuhi aturan.", reason=problem)
        ph = hash_password(pw)
        t = now()
        with dbm.tx(conn):
            conn.execute("UPDATE users SET password_hash=?, must_change_password=1, password_changed_at=? WHERE id=?", (ph, t, user_id))
            conn.execute("UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (t, user_id))
            conn.execute("DELETE FROM login_attempts WHERE key=?", (f"u:{row['username'].lower()}",))
            audit(conn, "password_reset", user_id=user_id, username=row["username"], ip=ip, detail=f"by={actor}")
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return public_user(row), pw


def unlock_user(username: str, settings: Settings | None = None) -> None:
    s = settings or get_settings()
    with dbm.session(s.db_path) as conn:
        conn.execute("DELETE FROM login_attempts WHERE key=?", (f"u:{username.strip().lower()}",))
        audit(conn, "account_unlocked", username=username)


# ---------- login & sesi ----------

def _register_failure(conn, key: str, limit: int, s: Settings, t: int) -> bool:
    """Catat satu kegagalan. Kembalikan True bila baru saja terkunci."""
    row = conn.execute("SELECT * FROM login_attempts WHERE key=?", (key,)).fetchone()
    failed = 0 if (row is None or t - row["updated_at"] > s.lock_seconds) else row["failed"]
    failed += 1
    locked_until = 0
    just_locked = False
    if failed >= limit:
        locked_until, failed, just_locked = t + s.lock_seconds, 0, True
    conn.execute(
        "INSERT INTO login_attempts(key,failed,locked_until,updated_at) VALUES (?,?,?,?)"
        " ON CONFLICT(key) DO UPDATE SET failed=excluded.failed, locked_until=excluded.locked_until, updated_at=excluded.updated_at",
        (key, failed, locked_until, t),
    )
    return just_locked


def authenticate(username: str, password: str, *, ip: str | None, user_agent: str | None,
                 settings: Settings | None = None) -> tuple[dict, str]:
    s = settings or get_settings()
    uname = (username or "").strip()
    ukey, ikey = f"u:{uname.lower()}", f"ip:{ip or '-'}"
    t = now()
    with dbm.session(s.db_path) as conn:
        # 1) sedang terkunci?
        for key in (ukey, ikey):
            r = conn.execute("SELECT locked_until FROM login_attempts WHERE key=?", (key,)).fetchone()
            if r and r["locked_until"] > t:
                wait = r["locked_until"] - t
                audit(conn, "login_locked", username=uname, ip=ip)
                raise AuthError(429, "account_locked", "Terlalu banyak percobaan. Coba lagi nanti.",
                                headers={"Retry-After": str(wait)}, retry_after_seconds=wait)
        # 2) verifikasi (selalu hitung hash agar waktu respons sama)
        row = conn.execute("SELECT * FROM users WHERE username=?", (uname,)).fetchone()
        ok = verify_password(password, row["password_hash"] if row else DUMMY_HASH)
        if not (ok and row and row["is_active"]):
            with dbm.tx(conn):
                _register_failure(conn, ikey, s.ip_max_failed, s, t)
                locked = _register_failure(conn, ukey, s.max_failed, s, t)
                reason = "inactive" if (ok and row and not row["is_active"]) else "bad_credentials"
                audit(conn, "login_failed", user_id=row["id"] if row else None, username=uname, ip=ip, detail=reason)
                if locked:
                    audit(conn, "account_locked", user_id=row["id"] if row else None, username=uname, ip=ip)
            raise AuthError(401, "invalid_credentials", "Username atau password salah.")
        # 3) sukses -> buat sesi
        token = new_token()
        with dbm.tx(conn):
            conn.execute("DELETE FROM login_attempts WHERE key=?", (ukey,))
            conn.execute(
                "INSERT INTO sessions(token_hash,user_id,created_at,last_seen_at,expires_at,ip,user_agent) VALUES (?,?,?,?,?,?,?)",
                (hash_token(token), row["id"], t, t, t + s.session_max_seconds, ip, (user_agent or "")[:200]),
            )
            conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (t, row["id"]))
            conn.execute("DELETE FROM sessions WHERE expires_at < ? OR (revoked_at IS NOT NULL AND revoked_at < ?)", (t - 86400, t - 86400))
            audit(conn, "login_success", user_id=row["id"], username=row["username"], ip=ip)
        row = conn.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    return public_user(row), token


def validate_session(token: str | None, settings: Settings | None = None) -> dict | None:
    if not token:
        return None
    s = settings or get_settings()
    th = hash_token(token)
    t = now()
    with dbm.session(s.db_path) as conn:
        r = conn.execute(
            "SELECT s.*, u.username, u.display_name, u.role, u.is_active, u.must_change_password"
            " FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (th,),
        ).fetchone()
        if not r or r["revoked_at"] is not None or not r["is_active"]:
            return None
        if t >= r["expires_at"] or t - r["last_seen_at"] > s.session_idle_seconds:
            conn.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL", (t, th))
            return None
        if t - r["last_seen_at"] >= _TOUCH_EVERY:
            conn.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (t, th))
    user = public_user({**dict(r), "id": r["user_id"]})
    user["session"] = th
    return user


def revoke_session(token: str | None, settings: Settings | None = None, *, ip: str | None = None) -> None:
    if not token:
        return
    s = settings or get_settings()
    th = hash_token(token)
    with dbm.session(s.db_path) as conn:
        r = conn.execute("SELECT s.user_id, u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (th,)).fetchone()
        conn.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL", (now(), th))
        if r:
            audit(conn, "logout", user_id=r["user_id"], username=r["username"], ip=ip)


def change_password(user: dict, current: str, new: str, *, settings: Settings | None = None, ip: str | None = None) -> None:
    s = settings or get_settings()
    with dbm.session(s.db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not row or not verify_password(current, row["password_hash"]):
            with dbm.tx(conn):
                audit(conn, "password_change_failed", user_id=user["id"], username=user["username"], ip=ip)
            raise AuthError(400, "wrong_current_password", "Password saat ini salah.")
        if verify_password(new, row["password_hash"]):
            raise AuthError(422, "weak_password", "Password baru harus berbeda dari yang lama.", reason="same_as_old")
        problem = password_problem(new, row["username"])
        if problem:
            raise AuthError(422, "weak_password", "Password belum memenuhi aturan.", reason=problem)
        ph = hash_password(new)
        t = now()
        with dbm.tx(conn):
            conn.execute("UPDATE users SET password_hash=?, must_change_password=0, password_changed_at=? WHERE id=?", (ph, t, user["id"]))
            conn.execute("UPDATE sessions SET revoked_at=? WHERE user_id=? AND token_hash<>? AND revoked_at IS NULL", (t, user["id"], user["session"]))
            audit(conn, "password_changed", user_id=user["id"], username=user["username"], ip=ip)


def audit_entries(limit: int = 100, offset: int = 0, settings: Settings | None = None) -> list[dict]:
    s = settings or get_settings()
    limit = max(1, min(int(limit), 500))
    with dbm.session(s.db_path) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?", (limit, max(0, int(offset)))).fetchall()
    return [dict(r) for r in rows]
