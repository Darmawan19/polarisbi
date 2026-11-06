"""Log keputusan dan API status: upsert tanpa menimpa status, append-only, peran, CSRF, audit, pemicu."""
import asyncio
import sqlite3
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from insight_testutil import Clock, insert_item, insight_env, utc  # noqa: F401

from insight import db as dbm
from insight import decisions as D
from insight import overview as O
from insight import pipeline
from insight.config import get_settings

NOW = utc(2026, 11, 3, 3, 0, 0)
H = {"X-Requested-With": "polarisbi"}
PW = "Sangat-Kuat-2026"
KEY = "regulasi.dampak_peraturan:all"


def conn():
    return dbm.session(get_settings().db_path)


def seed_regulasi(score=60):
    with conn() as c:
        insert_item(c, id=f"r{score}", title=f"OJK terbitkan aturan baru {score}", source="rss.media",
                    score=score, category="regulasi", published_at=dbm.to_iso(NOW - timedelta(minutes=5)))


def decision(key=KEY, level="perlu_keputusan", title="Analisis dampak peraturan baru"):
    return {"key": key, "rule_id": key.split(":")[0], "level": level, "title": title}


@pytest.fixture(autouse=True)
def _clear_cache():
    O.invalidate()
    yield
    O.invalidate()


# ---------- upsert ----------

def test_upsert_new_then_update_never_overwrites_status(insight_env):
    with conn() as c:
        assert D.upsert_active(c, [decision()], NOW) == 1
        row = D.get_decision(c, KEY)
        assert row["status"] == "baru" and row["first_seen_at"] == row["last_seen_at"] == "2026-11-03T03:00:00Z"
        assert [(e["dari_status"], e["ke_status"], e["actor"]) for e in row["events"]] == [(None, "baru", "system")]
        D.set_status(c, KEY, "ditinjau", "cek tim legal", "analyst1", NOW + timedelta(minutes=1))
        later = NOW + timedelta(hours=2)
        assert D.upsert_active(c, [decision(level="pantau", title="Judul baru")], later) == 0
        row = D.get_decision(c, KEY)
    assert row["status"] == "ditinjau" and row["note"] == "cek tim legal" and row["updated_by"] == "analyst1"
    assert row["last_level"] == "pantau" and row["last_title"] == "Judul baru"
    assert row["first_seen_at"] == "2026-11-03T03:00:00Z" and row["last_seen_at"] == "2026-11-03T05:00:00Z"
    assert [e["ke_status"] for e in row["events"]] == ["baru", "ditinjau"]


def test_inactive_decision_stays_in_log(insight_env):
    with conn() as c:
        D.upsert_active(c, [decision(), decision("pasar_keuangan.unit_link:all")], NOW)
        D.upsert_active(c, [decision("pasar_keuangan.unit_link:all")], NOW + timedelta(hours=1))
        rows = {r["key"]: r for r in D.history(c)}
    assert set(rows) == {KEY, "pasar_keuangan.unit_link:all"}
    assert rows[KEY]["last_seen_at"] == "2026-11-03T03:00:00Z"
    assert list(rows)[0] == "pasar_keuangan.unit_link:all"        # terbaru dulu


def test_events_are_append_only(insight_env):
    with conn() as c:
        D.upsert_active(c, [decision()], NOW)
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("UPDATE insight_decision_event SET actor='x'")
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("DELETE FROM insight_decision_event")


def test_schema_is_additive_and_idempotent(insight_env):
    path = get_settings().db_path
    with conn() as c:
        before = {t: [r["name"] for r in c.execute(f"PRAGMA table_info({t})")]
                  for t in ("insight_items", "insight_digests", "insight_source_status")}
    dbm.init_schema(path)
    dbm.init_schema(path)
    with conn() as c:
        after = {t: [r["name"] for r in c.execute(f"PRAGMA table_info({t})")] for t in before}
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert before == after and {"insight_decision", "insight_decision_event"} <= tables


def test_after_refresh_callback_persists_active_decisions(insight_env, monkeypatch):
    monkeypatch.setattr(dbm, "utcnow", Clock(NOW))
    seed_regulasi()
    asyncio.run(D.after_refresh({"results": []}))
    with conn() as c:
        rows = D.history(c)
    assert [r["key"] for r in rows] == [KEY] and rows[0]["status"] == "baru"


# ---------- API ----------

@pytest.fixture
def app_client(insight_env, tmp_path, monkeypatch):
    from insight import setup_insight
    from polaris_auth import service, setup_auth

    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth.db"))
    for k in ("POLARIS_BOOTSTRAP_ADMIN_USER", "POLARIS_BOOTSTRAP_ADMIN_PASSWORD", "POLARIS_COOKIE_SECURE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(dbm, "utcnow", Clock(NOW))
    app = FastAPI()
    setup_auth(app)
    setup_insight(app)
    for name, role in (("admin1", "admin"), ("analyst1", "analyst"), ("viewer1", "viewer")):
        service.create_user(name, PW, role)   # pengguna KHUSUS TES di DB sementara
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def login(c, name):
    c.cookies.clear()
    assert c.post("/auth/login", json={"username": name, "password": PW}, headers=H).status_code == 200


def post_status(c, status="ditinjau", note=None, key=KEY, headers=H):
    return c.post(f"/api/insight/decisions/{key}/status", json={"status": status, "note": note}, headers=headers)


def test_setup_registers_existing_after_refresh_hook(app_client):
    assert D.after_refresh in pipeline.after_refresh_callbacks()
    assert D.persist_engine in O._on_compute


def test_overview_lazily_persists_and_merges_status(app_client):
    seed_regulasi()
    login(app_client, "viewer1")
    d = app_client.get("/api/insight/overview", headers=H).json()["decisions"][0]
    assert d["key"] == KEY and d["status"] == "baru" and d["first_seen_at"] == "2026-11-03T03:00:00Z"
    assert d["status_updated_at"] is None and d["status_updated_by"] is None and d["is_draft"] is True
    login(app_client, "analyst1")
    assert post_status(app_client, "disetujui", "lanjut ke komite").status_code == 200
    # status dari log tidak ikut cache: overview langsung menampilkan status baru
    d = app_client.get("/api/insight/overview", headers=H).json()["decisions"][0]
    assert d["status"] == "disetujui" and d["status_updated_by"] == "analyst1"
    assert d["status_note"] == "lanjut ke komite" and d["status_updated_at"] == "2026-11-03T03:00:00Z"


def test_status_roles_csrf_validation_and_audit(app_client):
    from polaris_auth import service

    seed_regulasi()
    login(app_client, "viewer1")
    app_client.get("/api/insight/overview", headers=H)
    r = post_status(app_client)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    login(app_client, "analyst1")
    r = post_status(app_client, headers={})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "csrf"
    r = post_status(app_client, "selesai")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_status"
    r = post_status(app_client, "ditunda", "x" * 501)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_note"
    r = post_status(app_client, key="tidak.ada:all")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "decision_not_found"
    r = post_status(app_client, "ditinjau", "cek")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ditinjau" and body["note"] == "cek" and body["updated_by"] == "analyst1"
    assert [(e["dari_status"], e["ke_status"]) for e in body["events"]] == [(None, "baru"), ("baru", "ditinjau")]
    login(app_client, "admin1")
    assert post_status(app_client, "ditolak").status_code == 200
    events = [e for e in service.audit_entries(50) if e["event"] == "insight_decision_status"]
    assert len(events) == 2
    assert events[0]["username"] == "admin1" and f"key={KEY} from=ditinjau to=ditolak" in events[0]["detail"]
    assert events[1]["username"] == "analyst1" and "from=baru to=ditinjau" in events[1]["detail"]


def test_history_endpoint(app_client):
    seed_regulasi()
    login(app_client, "viewer1")
    app_client.get("/api/insight/overview", headers=H)
    r = app_client.get("/api/insight/decisions/history?limit=5", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 5 and body["statuses"] == list(D.STATUSES)
    item = body["items"][0]
    assert item["key"] == KEY and item["status"] == "baru" and item["events"][0]["actor"] == "system"
    assert app_client.get("/api/insight/decisions/history?limit=9999", headers=H).json()["limit"] == 200


def test_new_endpoints_require_login(app_client):
    for path in ("/api/insight/overview", "/api/insight/decisions/history", "/api/insight/products/COZY"):
        assert app_client.get(path, headers=H).status_code == 401
    assert post_status(app_client).status_code == 401
