"""Hash password, token sesi, dan aturan password. Hanya library standar Python."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets

# scrypt: N=2^15, r=8, p=1 (rekomendasi minimum OWASP). Parameter ikut tersimpan di hash,
# jadi bisa dinaikkan nanti tanpa merusak password lama.
_N, _R, _P, _DKLEN = 2**15, 8, 1, 32
_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, maxmem=_MAXMEM, dklen=_DKLEN)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p),
            maxmem=_MAXMEM, dklen=len(expected),
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


# Dipakai agar waktu respons sama untuk username yang tidak ada (mencegah penebakan username).
DUMMY_HASH = hash_password("tidak-dipakai-untuk-login")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_USERNAME_RE = re.compile(r"^[A-Za-z0-9._@-]{3,50}$")
_COMMON = {
    "password", "password1", "password123", "passw0rd", "12345678", "123456789", "1234567890",
    "qwertyuiop", "qwerty123", "admin12345", "welcome123", "letmein123", "iloveyou123",
    "polarisbi", "polarisbi123", "brilife123", "brilife2024", "brilife2026",
}


def validate_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(username or ""))


def password_problem(password: str, username: str = "") -> str | None:
    """Kembalikan kode masalah, atau None bila password diterima."""
    if len(password) < 10:
        return "too_short"
    if len(password) > 128:
        return "too_long"
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "needs_letter_and_digit"
    low = password.lower()
    if low in _COMMON:
        return "too_common"
    if username and len(username) >= 3 and username.lower() in low:
        return "contains_username"
    return None


_TEMP_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"  # tanpa huruf yang mirip
_TEMP_DIGITS = "23456789"


def generate_temp_password(length: int = 14) -> str:
    while True:
        chars = [secrets.choice(_TEMP_ALPHABET + _TEMP_DIGITS) for _ in range(length)]
        pw = "".join(chars)
        if any(c in _TEMP_DIGITS for c in pw) and any(c in _TEMP_ALPHABET for c in pw):
            return pw
