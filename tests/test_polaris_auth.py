import importlib
import sqlite3
import sys
import time
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polaris_auth import service, setup_auth  # noqa: E402
from polaris_auth import security  # noqa: E402

H = {"X-Requested-With": "polarisbi"}
ORIGIN = "http://localhost:3000"
GOOD = "Sangat-Kuat-2026"


class Clock:
    def __init__(self):
        self.t = int(time.time())

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(service, "now", c)
    return c


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth.db"))
    for k in ("POLARIS_COOKIE_SECURE", "POLARIS_SESSION_IDLE_MIN", "POLARIS_SESSION_MAX_HOURS",
              "POLARIS_MAX_FAILED", "POLARIS_LOCK_MIN", "POLARIS_BOOTSTRAP_ADMIN_USER", "POLARIS_BOOTSTRAP_ADMIN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def make_app(cors_first=True):
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    @app.post("/api/echo")
    def echo(payload: dict):
        return payload

    @app.get("/api/admin-only")
    def admin_only(user=Depends(__import__("polaris_auth").require_role("admin"))):
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def add_cors():
        app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])

    if cors_first:
        add_cors()
        setup_auth(app)
    else:
        setup_auth(app)
        add_cors()
    return app


@pytest.fixture
def client(env, clock):
    app = make_app()
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def mk(username="admin1", role="admin", pw=GOOD, must_change=False, name=None):
    return service.create_user(username, pw, role, display_name=name, must_change=must_change)


def login(client, username="admin1", pw=GOOD, expect=200):
    r = client.post("/auth/login", json={"username": username, "password": pw}, headers=H)
    assert r.status_code == expect, r.text
    return r


# ---------- dasar ----------

def test_api_requires_login_and_401_has_cors(client):
    r = client.get("/api/ping", headers={"Origin": ORIGIN})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "not_authenticated"
    assert r.headers["access-control-allow-origin"] == ORIGIN
    assert r.headers["access-control-allow-credentials"] == "true"


def test_public_paths_stay_public(client):
    assert client.get("/health").status_code == 200


def test_preflight_is_not_blocked(client):
    r = client.options("/api/echo", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                                             "Access-Control-Request-Headers": "content-type,x-requested-with"})
    assert r.status_code == 200
    assert "x-requested-with" in r.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize("cors_first", [True, False])
def test_cors_outermost_regardless_of_order(env, clock, cors_first):
    with TestClient(make_app(cors_first)) as c:
        r = c.get("/api/ping", headers={"Origin": ORIGIN})
        assert r.status_code == 401 and r.headers.get("access-control-allow-origin") == ORIGIN


def test_login_success_cookie_flags_and_me(client):
    mk()
    r = login(client)
    assert r.json()["user"]["username"] == "admin1"
    assert GOOD not in r.text and "password_hash" not in r.text
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc and "path=/" in sc
    assert "secure" not in sc  # default dev (http)
    assert client.get("/auth/me").json()["user"]["role"] == "admin"
    assert client.get("/api/ping").json() == {"pong": True}


def test_secure_flag_when_enabled(env, clock, monkeypatch):
    monkeypatch.setenv("POLARIS_COOKIE_SECURE", "true")
    with TestClient(make_app(), base_url="https://testserver") as c:
        mk()
        r = login(c)
        assert "secure" in r.headers["set-cookie"].lower()


def test_wrong_password_and_unknown_user_look_identical(client):
    mk()
    a = login(client, pw="salah-salah-1", expect=401).json()
    b = login(client, username="tidak-ada", pw="salah-salah-1", expect=401).json()
    assert a == b and a["detail"]["code"] == "invalid_credentials"


def test_csrf_header_required(client):
    mk()
    r = client.post("/auth/login", json={"username": "admin1", "password": GOOD})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "csrf"
    login(client)
    assert client.post("/api/echo", json={"a": 1}).status_code == 403
    assert client.post("/api/echo", json={"a": 1}, headers=H).json() == {"a": 1}


def test_passwords_and_tokens_not_stored_in_clear(client, env):
    mk()
    r = login(client)
    token = client.cookies.get("polarisbi_session")
    raw = Path(env / "auth.db").read_bytes() + (Path(str(env / "auth.db") + "-wal").read_bytes() if Path(str(env / "auth.db") + "-wal").exists() else b"")
    assert GOOD.encode() not in raw
    assert token.encode() not in raw
    h = sqlite3.connect(env / "auth.db").execute("select password_hash from users").fetchone()[0]
    assert h.startswith("scrypt$") and security.verify_password(GOOD, h) and not security.verify_password("x", h)


# ---------- kunci akun ----------

def test_lockout_after_failures_even_for_unknown_user(client, clock):
    mk()
    for _ in range(5):
        login(client, pw="salah-salah-1", expect=401)
    r = login(client, pw=GOOD, expect=429)  # password benar pun ditolak saat terkunci
    d = r.json()["detail"]
    assert d["code"] == "account_locked" and d["retry_after_seconds"] > 0 and r.headers["retry-after"]
    for _ in range(5):
        login(client, username="hantu", pw="x" * 12, expect=401)
    assert login(client, username="hantu", pw="x" * 12, expect=429)  # tidak bisa dibedakan -> tidak bocor
    clock.advance(16 * 60)
    login(client)  # kunci kedaluwarsa


def test_successful_login_resets_counter(client):
    mk()
    for _ in range(4):
        login(client, pw="salah-salah-1", expect=401)
    login(client)
    for _ in range(4):
        login(client, pw="salah-salah-1", expect=401)
    login(client)  # tidak terkunci karena hitungan direset


# ---------- sesi ----------

def test_idle_timeout_and_activity_extends(client, clock):
    mk()
    login(client)
    clock.advance(50 * 60)
    assert client.get("/api/ping").status_code == 200   # aktivitas memperpanjang
    clock.advance(50 * 60)
    assert client.get("/api/ping").status_code == 200
    clock.advance(61 * 60)
    assert client.get("/api/ping").status_code == 401   # idle > 60 menit


def test_absolute_lifetime(client, clock):
    mk()
    login(client)
    for _ in range(14):
        clock.advance(55 * 60)
        r = client.get("/api/ping")
        if r.status_code == 401:
            break
    assert r.status_code == 401  # lewat 12 jam


def test_logout_revokes_server_side(client):
    mk()
    login(client)
    token = client.cookies.get("polarisbi_session")
    assert client.post("/auth/logout", headers=H).json() == {"ok": True}
    client.cookies.set("polarisbi_session", token)  # penyerang memakai token curian
    assert client.get("/api/ping").status_code == 401
    assert client.get("/auth/me").status_code == 401


# ---------- ganti password ----------

def test_forced_password_change_flow(client):
    mk("budi", "analyst", pw="Sementara-2026", must_change=True)
    login(client, "budi", "Sementara-2026")
    assert client.get("/auth/me").json()["user"]["must_change_password"] is True
    r = client.get("/api/ping")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "password_change_required"
    bad = client.post("/auth/change-password", json={"current_password": "keliru-keliru1", "new_password": "BaruKuat-2027"}, headers=H)
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "wrong_current_password"
    weak = client.post("/auth/change-password", json={"current_password": "Sementara-2026", "new_password": "pendek1"}, headers=H)
    assert weak.status_code == 422 and weak.json()["detail"]["reason"] == "too_short"
    same = client.post("/auth/change-password", json={"current_password": "Sementara-2026", "new_password": "Sementara-2026"}, headers=H)
    assert same.status_code == 422
    ok = client.post("/auth/change-password", json={"current_password": "Sementara-2026", "new_password": "BaruKuat-2027"}, headers=H)
    assert ok.status_code == 200
    assert client.get("/api/ping").status_code == 200
    client.post("/auth/logout", headers=H)
    login(client, "budi", "Sementara-2026", expect=401)
    login(client, "budi", "BaruKuat-2027")


def test_password_change_revokes_other_sessions(env, clock):
    app = make_app()
    mk()
    with TestClient(app) as a, TestClient(app) as b:
        login(a); login(b)
        r = a.post("/auth/change-password", json={"current_password": GOOD, "new_password": "BaruKuat-2027"}, headers=H)
        assert r.status_code == 200
        assert a.get("/api/ping").status_code == 200   # sesi yang dipakai tetap hidup
        assert b.get("/api/ping").status_code == 401   # sesi lain dicabut


@pytest.mark.parametrize("pw,reason", [("abc", "too_short"), ("hanyahurufsaja", "needs_letter_and_digit"),
                                       ("1234567890", "needs_letter_and_digit"), ("password123", "too_common"),
                                       ("x" * 130 + "1", "too_long"), ("andi-andi-2026", "contains_username")])
def test_password_policy(pw, reason):
    assert security.password_problem(pw, "andi") == reason
    assert security.password_problem(GOOD, "andi") is None


# ---------- peran & admin ----------

def test_roles_and_admin_management(client):
    mk()
    mk("rina", "analyst")
    login(client, "rina")
    assert client.get("/auth/users").status_code == 403
    assert client.get("/api/admin-only").status_code == 403
    assert client.get("/api/ping").status_code == 200
    client.post("/auth/logout", headers=H)

    login(client)
    assert client.get("/api/admin-only").status_code == 200
    users = client.get("/auth/users").json()["users"]
    assert {u["username"] for u in users} == {"admin1", "rina"}
    assert all("password" not in u and "password_hash" not in u for u in users)

    r = client.post("/auth/users", json={"username": "sari", "role": "viewer", "display_name": "Sari"}, headers=H)
    assert r.status_code == 201
    temp = r.json()["temporary_password"]
    assert r.json()["user"]["must_change_password"] is True and security.password_problem(temp, "sari") is None
    assert client.post("/auth/users", json={"username": "SARI", "role": "viewer"}, headers=H).status_code == 409
    assert client.post("/auth/users", json={"username": "x", "role": "viewer"}, headers=H).status_code == 422
    assert client.post("/auth/users", json={"username": "tono", "role": "boss"}, headers=H).status_code == 422
    client.post("/auth/logout", headers=H)
    login(client, "sari", temp)  # password sementara bisa dipakai
    client.post("/auth/logout", headers=H)


def test_disable_user_kills_sessions_and_blocks_login(env, clock):
    app = make_app()
    admin = mk(); mk("rina", "analyst")
    with TestClient(app) as adm, TestClient(app) as usr:
        login(adm); login(usr, "rina")
        rid = next(u["id"] for u in adm.get("/auth/users").json()["users"] if u["username"] == "rina")
        assert adm.patch(f"/auth/users/{rid}", json={"is_active": False}, headers=H).status_code == 200
        assert usr.get("/api/ping").status_code == 401
        login(usr, "rina", expect=401)
        assert adm.patch(f"/auth/users/{rid}", json={"is_active": True}, headers=H).status_code == 200
        login(usr, "rina")


def test_admin_safeguards(client):
    a = mk()
    login(client)
    r = client.patch(f"/auth/users/{a['id']}", json={"role": "viewer"}, headers=H)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "cannot_demote_self"
    r = client.patch(f"/auth/users/{a['id']}", json={"is_active": False}, headers=H)
    assert r.status_code == 400
    b = mk("admin2", "admin")
    assert client.patch(f"/auth/users/{b['id']}", json={"role": "analyst"}, headers=H).status_code == 200  # masih ada admin1
    assert client.patch("/auth/users/9999", json={"role": "analyst"}, headers=H).status_code == 404


def test_admin_reset_password(env, clock):
    app = make_app()
    mk(); u = mk("rina", "analyst")
    with TestClient(app) as adm, TestClient(app) as usr:
        login(adm); login(usr, "rina")
        r = adm.post(f"/auth/users/{u['id']}/reset-password", headers=H)
        temp = r.json()["temporary_password"]
        assert usr.get("/api/ping").status_code == 401  # sesi lama dicabut
        login(usr, "rina", GOOD, expect=401)
        login(usr, "rina", temp)
        assert usr.get("/api/ping").status_code == 403  # wajib ganti password


def test_audit_log(client):
    mk(); mk("rina", "analyst")
    login(client, "rina", pw="salah-salah-1", expect=401)
    login(client)
    ev = [e["event"] for e in client.get("/auth/audit").json()["entries"]]
    assert "login_failed" in ev and "login_success" in ev and "user_created" in ev
    assert all(GOOD not in str(e) and "scrypt" not in str(e) for e in client.get("/auth/audit").json()["entries"])
    client.post("/auth/logout", headers=H)
    login(client, "rina")
    assert client.get("/auth/audit").status_code == 403


def test_bootstrap_admin_only_when_empty(env, clock, monkeypatch):
    monkeypatch.setenv("POLARIS_BOOTSTRAP_ADMIN_USER", "root")
    monkeypatch.setenv("POLARIS_BOOTSTRAP_ADMIN_PASSWORD", "Awal-Sangat-2026")
    with TestClient(make_app()) as c:
        r = login(c, "root", "Awal-Sangat-2026")
        assert r.json()["user"]["must_change_password"] is True and r.json()["user"]["role"] == "admin"
    monkeypatch.setenv("POLARIS_BOOTSTRAP_ADMIN_USER", "root2")
    service.init_auth()
    assert [u["username"] for u in service.list_users()] == ["root"]  # tidak menambah lagi


def test_cli(env, monkeypatch, capsys):
    from polaris_auth import manage
    monkeypatch.setattr(manage.getpass, "getpass", lambda *_: GOOD)
    manage.main(["create-user", "dewi", "--role", "viewer", "--name", "Dewi"])
    manage.main(["list-users"])
    out = capsys.readouterr().out
    assert "dewi" in out and "viewer" in out
    manage.main(["reset-password", "dewi"])
    assert "Password sementara" in capsys.readouterr().out
    manage.main(["disable", "dewi"]); manage.main(["unlock", "dewi"])
    with pytest.raises(SystemExit):
        manage.main(["reset-password", "tidak-ada"])
