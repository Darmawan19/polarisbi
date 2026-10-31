"""CLI pengelolaan akun.

  python -m polaris_auth.manage create-user USERNAME --role admin --name "Nama Lengkap"
  python -m polaris_auth.manage list-users
  python -m polaris_auth.manage reset-password USERNAME
  python -m polaris_auth.manage disable USERNAME | enable USERNAME
  python -m polaris_auth.manage unlock USERNAME
"""
from __future__ import annotations

import argparse
import getpass
import sys

from . import db as dbm
from . import service
from .config import get_settings
from .errors import AuthError


def _find(username: str):
    s = get_settings()
    with dbm.session(s.db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
    if not row:
        sys.exit(f"Pengguna '{username}' tidak ditemukan.")
    return row


def _ask_password() -> str:
    p1 = getpass.getpass("Password: ")
    p2 = getpass.getpass("Ulangi password: ")
    if p1 != p2:
        sys.exit("Password tidak sama.")
    return p1


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="polaris_auth.manage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("username")
    c.add_argument("--role", default="analyst", choices=service.ROLES)
    c.add_argument("--name")
    c.add_argument("--no-force-change", action="store_true", help="tidak wajibkan ganti password saat login pertama")
    sub.add_parser("list-users")
    for name in ("reset-password", "disable", "enable", "unlock"):
        sub.add_parser(name).add_argument("username")
    a = ap.parse_args(argv)

    s = get_settings()
    service.init_auth(s)
    try:
        if a.cmd == "create-user":
            u = service.create_user(a.username, _ask_password(), a.role, display_name=a.name,
                                    must_change=not a.no_force_change, actor="cli")
            print(f"Dibuat: {u['username']} ({u['role']})")
        elif a.cmd == "list-users":
            for u in service.list_users(s):
                flag = "" if u["is_active"] else "  [NONAKTIF]"
                print(f"{u['id']:>3}  {u['username']:<24} {u['role']:<8} {u['display_name']}{flag}")
        elif a.cmd == "reset-password":
            row = _find(a.username)
            _, pw = service.reset_password(row["id"], actor="cli", settings=s)
            print(f"Password sementara untuk {a.username}: {pw}\n(wajib diganti saat login berikutnya; semua sesi lama dicabut)")
        elif a.cmd in ("disable", "enable"):
            row = _find(a.username)
            actor = {"id": -1, "username": "cli"}
            service.update_user(row["id"], actor=actor, is_active=(a.cmd == "enable"), settings=s)
            print(f"{a.username}: {'aktif' if a.cmd == 'enable' else 'dinonaktifkan'}")
        elif a.cmd == "unlock":
            service.unlock_user(a.username, s)
            print(f"{a.username}: kunci akun dibuka")
    except AuthError as e:
        sys.exit(f"Gagal: {e.detail['message']}")


if __name__ == "__main__":
    main()
