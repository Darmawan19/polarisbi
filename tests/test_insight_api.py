"""API /api/insight/*: auth, peran, kontrak respons, error, audit."""
import asyncio
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from insight_testutil import Clock, insert_item, insight_env, utc  # noqa: F401

from insight import db as dbm
from insight import pipeline, setup_insight
from insight.config import get_settings
from polaris_auth import service, setup_auth

H = {"X-Requested-With": "polarisbi"}
PW = "Sangat-Kuat-2026"

FEED_KEYS = {"id", "source", "source_label", "attribution", "title", "snippet", "url", "published_at", "fetched_at",
             "category", "province", "score", "severity_label", "severity_verified"}
DIGEST_KEYS = {"status", "period", "language", "bucket_key", "period_start", "period_end", "generated_at",
               "generated_by", "is_stale", "content", "impact", "exposure_is_demo", "items", "attributions"}


@pytest.fixture
def app_client(insight_env, tmp_path, monkeypatch):
    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth.db"))
    for k in ("POLARIS_BOOTSTRAP_ADMIN_USER", "POLARIS_BOOTSTRAP_ADMIN_PASSWORD", "POLARIS_COOKIE_SECURE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(dbm, "utcnow", Clock(utc(2026, 11, 3, 3, 0, 0)))
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    setup_auth(app)
    setup_insight(app)
    # pengguna KHUSUS TES di DB sementara (bukan akun nyata)
    for name, role in (("admin1", "admin"), ("analyst1", "analyst"), ("viewer1", "viewer")):
        service.create_user(name, PW, role)
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def login(c, name):
    c.cookies.clear()
    r = c.post("/auth/login", json={"username": name, "password": PW}, headers=H)
    assert r.status_code == 200, r.text


def seed():
    with dbm.session(get_settings().db_path) as conn:
        insert_item(conn, id="a", title="Gempa M6.0 Papua", source="bmkg_quake", score=80, province="Papua",
                    published_at="2026-11-03T01:00:00Z", attribution="Sumber: BMKG", source_label="BMKG Gempabumi")
        insert_item(conn, id="b", title="Inflasi naik", score=40, category="ekonomi_makro",
                    published_at="2026-11-03T02:00:00Z")
        insert_item(conn, id="c", title="OJK aturan baru", score=45, category="regulasi", province="DKI Jakarta",
                    published_at="2026-11-02T20:00:00Z")


ENDPOINTS = [("get", "/api/insight/feed"), ("get", "/api/insight/digest?period=daily"),
             ("post", "/api/insight/digest/generate"), ("post", "/api/insight/refresh"),
             ("get", "/api/insight/sources"), ("get", "/api/insight/exposure")]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_401_without_login(app_client, method, path):
    r = getattr(app_client, method)(path, headers=H)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "not_authenticated"


def test_post_without_csrf_header_is_403(app_client):
    login(app_client, "admin1")
    r = app_client.post("/api/insight/refresh")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "csrf"


@pytest.mark.parametrize("user,path", [("viewer1", "/api/insight/digest/generate"), ("viewer1", "/api/insight/refresh"),
                                       ("analyst1", "/api/insight/refresh")])
def test_403_wrong_role(app_client, user, path):
    login(app_client, user)
    r = app_client.post(path, json={"period": "daily"}, headers=H)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"


@pytest.mark.parametrize("user", ["viewer1", "analyst1", "admin1"])
def test_all_roles_can_read(app_client, user):
    login(app_client, user)
    for path in ("/api/insight/feed", "/api/insight/digest?period=weekly", "/api/insight/sources",
                 "/api/insight/exposure"):
        assert app_client.get(path, headers=H).status_code == 200, path


def test_feed_shape_filters_and_paging(app_client):
    seed()
    login(app_client, "viewer1")
    r = app_client.get("/api/insight/feed", headers=H).json()
    assert set(r) == {"items", "total", "limit", "offset"}
    assert r["total"] == 3 and r["limit"] == 50 and r["offset"] == 0
    assert [i["id"] for i in r["items"]] == ["a", "c", "b"]
    it = r["items"][0]
    assert set(it) == FEED_KEYS
    assert it["severity_label"] == "sangat_tinggi" and it["severity_verified"] is False and it["score"] == 80
    assert it["published_at"].endswith("Z") and it["fetched_at"].endswith("Z")
    g = lambda q: app_client.get("/api/insight/feed" + q, headers=H)  # noqa: E731
    assert [i["id"] for i in g("?category=regulasi").json()["items"]] == ["c"]
    assert [i["id"] for i in g("?province=Jakarta").json()["items"]] == ["c"]   # alias diterima
    assert [i["id"] for i in g("?min_score=45").json()["items"]] == ["a", "c"]
    assert [i["id"] for i in g("?since=2026-11-03T00:00:00Z").json()["items"]] == ["a", "b"]
    page = g("?limit=1&offset=1").json()
    assert page["total"] == 3 and [i["id"] for i in page["items"]] == ["c"] and page["limit"] == 1
    assert g("?limit=1000").json()["limit"] == 200
    assert g("?category=xx").status_code == 422 and g("?category=xx").json()["detail"]["code"] == "invalid_category"
    assert g("?since=kemarin").json()["detail"]["code"] == "invalid_since"


def test_digest_get_not_generated_shape(app_client):
    login(app_client, "viewer1")
    r = app_client.get("/api/insight/digest?period=daily", headers=H).json()
    assert set(r) == DIGEST_KEYS
    assert r["status"] == "not_generated" and r["content"] is None and r["impact"] == [] and r["items"] == []
    assert r["language"] == "id" and r["exposure_is_demo"] is True and r["bucket_key"] is None


@pytest.mark.parametrize("q", ["", "?period=yearly"])
def test_digest_get_invalid_period_422(app_client, q):
    login(app_client, "viewer1")
    r = app_client.get("/api/insight/digest" + q, headers=H)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_period"


def test_generate_flow_shape_cooldown_and_audit(app_client, monkeypatch):
    monkeypatch.setenv("INSIGHT_GENERATE_COOLDOWN_SECONDS", "60")
    seed()
    login(app_client, "analyst1")
    bad = app_client.post("/api/insight/digest/generate", json={"period": "hourly"}, headers=H)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_period"
    missing = app_client.post("/api/insight/digest/generate", json={}, headers=H)
    assert missing.status_code == 422 and missing.json()["detail"]["code"] == "invalid_period"

    r = app_client.post("/api/insight/digest/generate", json={"period": "daily"}, headers=H)
    assert r.status_code == 200
    d = r.json()
    assert set(d) == DIGEST_KEYS
    assert d["status"] == "fallback" and d["generated_by"] == "template" and d["language"] == "id"
    assert d["exposure_is_demo"] is True and d["bucket_key"] == "2026-11-03"
    assert all(t.endswith("Z") for t in (d["period_start"], d["period_end"], d["generated_at"]))
    assert set(d["content"]) == {"executive_summary", "key_events", "impact_note", "watchlist"}
    assert all(set(e) == {"text", "item_ids"} for e in d["content"]["key_events"])
    assert all(set(i) == FEED_KEYS for i in d["items"])
    imp = d["impact"][0]
    assert set(imp) == {"province", "events", "max_score", "total_active_policies", "exposure"}
    assert imp["province"] == "Papua" and set(imp["exposure"][0]) == {"product", "active_policies"}
    assert sorted(d["attributions"]) == ["Sumber: BMKG", "Sumber: GDELT Project"]

    got = app_client.get("/api/insight/digest?period=daily", headers=H).json()
    assert got["generated_at"] == d["generated_at"] and got["status"] == "fallback"

    cd = app_client.post("/api/insight/digest/generate", json={"period": "daily", "force": True}, headers=H)
    assert cd.status_code == 429
    det = cd.json()["detail"]
    assert det["code"] == "cooldown" and isinstance(det["retry_after_seconds"], int) and det["retry_after_seconds"] > 0

    lang = app_client.post("/api/insight/digest/generate", json={"period": "daily", "language": "en"}, headers=H)
    assert lang.status_code == 422

    events = [e for e in service.audit_entries(50) if e["event"] == "insight_digest_generate"]
    assert any("status=fallback" in (e["detail"] or "") and e["username"] == "analyst1" for e in events)
    assert any("result=cooldown" in (e["detail"] or "") for e in events)


def test_refresh_admin_shape_and_audit(app_client, monkeypatch):
    async def fake_refresh(*a, **k):
        return {"results": [{"source": "bmkg_quake", "ok": True, "new_items": 3, "error": None},
                            {"source": "gdelt", "ok": False, "new_items": 0, "error": "HTTP 429 dari GDELT"}],
                "finished_at": "2026-11-03T03:00:00Z"}

    monkeypatch.setattr(pipeline, "refresh", fake_refresh)
    login(app_client, "admin1")
    r = app_client.post("/api/insight/refresh", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"results", "finished_at"}
    assert set(body["results"][0]) == {"source", "ok", "new_items", "error"}
    ev = [e for e in service.audit_entries(50) if e["event"] == "insight_refresh"]
    assert ev and ev[0]["username"] == "admin1" and "gdelt:error" in ev[0]["detail"]


def test_refresh_409_when_already_running(app_client, monkeypatch):
    release = threading.Event()

    class Blocking:
        name, label, attribution = "gdelt", "G", "Sumber: G"

        async def fetch(self, client):
            while not release.is_set():
                await asyncio.sleep(0.02)
            return []

    monkeypatch.setenv("INSIGHT_SOURCES", "gdelt")
    background = threading.Thread(
        target=lambda: asyncio.run(pipeline.refresh(get_settings(), adapters=[Blocking()])))
    background.start()
    try:
        for _ in range(100):
            if pipeline.is_running():
                break
            time.sleep(0.01)
        login(app_client, "admin1")
        r = app_client.post("/api/insight/refresh", headers=H)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "already_running"
    finally:
        release.set()
        background.join(5)


def test_sources_shape_and_status(app_client, monkeypatch):
    monkeypatch.setenv("INSIGHT_SOURCES", "bmkg_quake,who_don")
    monkeypatch.setenv("INSIGHT_RSS_FEEDS", "Kantor Berita=https://example.org/rss")
    with dbm.session(get_settings().db_path) as conn:
        conn.execute("INSERT INTO insight_source_status VALUES ('bmkg_quake',1,'2026-11-03T02:50:00Z',"
                     "'2026-11-03T02:50:00Z',8,NULL)")
        conn.execute("INSERT INTO insight_source_status VALUES ('who_don',1,'2026-11-03T02:50:00Z',"
                     "'2026-11-02T00:00:00Z',3,'HTTP 503 dari WHO DON')")
    login(app_client, "viewer1")
    rows = app_client.get("/api/insight/sources", headers=H).json()
    by = {r["source"]: r for r in rows}
    assert set(by) == {"bmkg_quake", "bmkg_weather", "who_don", "gdelt", "rss.kantor-berita"}
    assert all(set(r) == {"source", "label", "attribution", "enabled", "status", "last_attempt_at",
                          "last_success_at", "last_item_count", "last_error"} for r in rows)
    assert by["bmkg_quake"]["status"] == "ok" and by["bmkg_quake"]["last_item_count"] == 8
    assert by["who_don"]["status"] == "error"
    assert by["gdelt"]["status"] == "disabled" and by["gdelt"]["enabled"] is False
    assert by["rss.kantor-berita"]["status"] == "stale" and by["rss.kantor-berita"]["enabled"] is True
    assert by["rss.kantor-berita"]["attribution"] == "Sumber: Kantor Berita"
    assert by["bmkg_quake"]["attribution"] == "Sumber: BMKG" and by["gdelt"]["attribution"] == "Sumber: GDELT Project"


def test_sources_stale_after_three_intervals(app_client, monkeypatch):
    monkeypatch.setenv("INSIGHT_SOURCES", "bmkg_quake")
    monkeypatch.setenv("INSIGHT_REFRESH_MINUTES", "30")
    with dbm.session(get_settings().db_path) as conn:
        conn.execute("INSERT INTO insight_source_status VALUES ('bmkg_quake',1,'2026-11-03T01:29:00Z',"
                     "'2026-11-03T01:29:00Z',8,NULL)")   # 91 menit lalu
    login(app_client, "viewer1")
    by = {r["source"]: r for r in app_client.get("/api/insight/sources", headers=H).json()}
    assert by["bmkg_quake"]["status"] == "stale"


def test_exposure_is_demo(app_client):
    login(app_client, "viewer1")
    r = app_client.get("/api/insight/exposure", headers=H).json()
    assert set(r) == {"is_demo", "rows"} and r["is_demo"] is True
    assert len(r["rows"]) == 114 and set(r["rows"][0]) == {"province", "product", "active_policies"}


def test_unknown_exposure_provider_falls_back_to_demo(app_client, monkeypatch):
    monkeypatch.setenv("INSIGHT_EXPOSURE_PROVIDER", "warehouse")
    login(app_client, "viewer1")
    assert app_client.get("/api/insight/exposure", headers=H).json()["is_demo"] is True


def test_scheduler_off_by_default_and_lifespan_ok(insight_env, monkeypatch, tmp_path):
    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth2.db"))
    app = FastAPI()
    setup_auth(app)
    setup_insight(app)
    with TestClient(app):
        assert app.state.insight_scheduler.running is False


def test_scheduler_starts_and_stops_cleanly(insight_env, monkeypatch, tmp_path):
    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth3.db"))
    monkeypatch.setenv("INSIGHT_SCHEDULER", "on")
    calls = []

    async def fake_refresh(*a, **k):
        calls.append(1)
        return {"results": [], "finished_at": "x"}

    monkeypatch.setattr(pipeline, "refresh", fake_refresh)
    app = FastAPI()
    setup_auth(app)
    setup_insight(app)
    with TestClient(app):
        for _ in range(100):
            if calls:
                break
            time.sleep(0.01)
        assert app.state.insight_scheduler.running is True
    assert calls and app.state.insight_scheduler.running is False


def test_refresh_minutes_minimum_5(monkeypatch):
    monkeypatch.setenv("INSIGHT_REFRESH_MINUTES", "1")
    assert get_settings().refresh_minutes == 5
