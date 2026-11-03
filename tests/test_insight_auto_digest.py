"""Ronde 2: pemicu pasca-refresh, ringkasan otomatis, latar belakang sumber lambat, dan scheduler."""
import asyncio
import json
import time
from datetime import timedelta

import pytest

from insight_testutil import Clock, insert_item, insight_env, utc  # noqa: F401

from insight import auto_digest as A
from insight import db as dbm
from insight import digest as D
from insight import llm as insight_llm
from insight import pipeline
from insight.config import get_settings
from insight.models import RawItem
from insight.scheduler import InsightScheduler
from polaris_auth import service

NOW = utc(2026, 11, 3, 3, 0, 0)   # 10:00 WIB


@pytest.fixture
def env(insight_env, tmp_path, monkeypatch):
    monkeypatch.setenv("INSIGHT_AUTO_DIGEST", "on")
    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth.db"))
    for k in ("POLARIS_BOOTSTRAP_ADMIN_USER", "POLARIS_BOOTSTRAP_ADMIN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    service.init_auth()
    clock = Clock(NOW)
    monkeypatch.setattr(dbm, "utcnow", clock)
    monkeypatch.setattr(insight_llm, "available", lambda: False)   # bawaan tes: tanpa kunci API
    return clock


@pytest.fixture
def no_hooks():
    saved = list(pipeline._after_refresh)
    pipeline._after_refresh.clear()
    yield
    pipeline._after_refresh[:] = saved


def run(coro):
    return asyncio.run(coro)


def seed(*rows):
    with dbm.session(get_settings().db_path) as conn:
        for r in rows:
            insert_item(conn, **r)


def item(id, score=70, published_at="2026-11-03T01:00:00Z", **kw):
    return dict(id=id, score=score, published_at=published_at, **kw)


def actions(result):
    return {r["period"]: (r["action"], r["result"]) for r in result}


def digest_row(period, key):
    with dbm.session(get_settings().db_path) as conn:
        return conn.execute("SELECT * FROM insight_digests WHERE period=? AND bucket_key=?", (period, key)).fetchone()


# ---------- aturan auto-digest ----------

def test_no_events_skips_all_periods(env):
    out = run(A.run_auto_digest())
    assert [r["period"] for r in out] == ["daily", "weekly", "monthly"]
    assert all(r["action"] == "no_events" and r["result"] == "skipped" for r in out)
    with dbm.session(get_settings().db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM insight_digests").fetchone()[0] == 0


def test_creates_missing_briefs_sequentially_with_auto_trigger_and_audit(env):
    seed(item("a"))
    out = run(A.run_auto_digest())
    assert [r["period"] for r in out] == ["daily", "weekly", "monthly"]
    assert all(r["action"] == "create" and r["result"] == "fallback:template" for r in out)
    for period in ("daily", "weekly", "monthly"):
        d = D.get_digest(period)
        assert d["status"] == "fallback" and d["generated_trigger"] == "auto" and d["generated_by"] == "template"
    ev = [e for e in service.audit_entries(50) if e["event"] == "insight_digest_auto"]
    assert len(ev) == 3 and all(e["username"] == "system" and e["user_id"] is None for e in ev)
    assert any("period=daily" in e["detail"] and "action=create" in e["detail"] for e in ev)


def test_only_periods_with_events_are_created(env):
    seed(item("old", published_at="2026-10-30T00:00:00Z"))   # di luar 24 jam, di dalam 7 hari
    assert actions(run(A.run_auto_digest())) == {"daily": ("no_events", "skipped"),
                                                 "weekly": ("create", "fallback:template"),
                                                 "monthly": ("create", "fallback:template")}


def test_suspicious_items_do_not_count_as_events(env):
    seed(item("x", meta_json=json.dumps({"suspicious": True})))
    assert all(r["action"] == "no_events" for r in run(A.run_auto_digest()))


def test_fresh_brief_is_not_regenerated(env):
    seed(item("a"))
    run(A.run_auto_digest())
    env.set(NOW + timedelta(hours=2))
    assert actions(run(A.run_auto_digest()))["daily"] == ("fresh", "skipped")   # tidak ada item baru


def test_stale_daily_regenerated_only_after_threshold(env):
    seed(item("a"))
    run(A.run_auto_digest())
    first = digest_row("daily", "2026-11-03")["generated_at"]
    # item baru berskor tinggi → brief stale
    env.set(NOW + timedelta(minutes=30))
    seed(item("b", score=85, published_at="2026-11-03T03:20:00Z", fetched_at="2026-11-03T03:25:00Z"))
    assert actions(run(A.run_auto_digest()))["daily"] == ("too_recent", "skipped")     # 30 < 60 menit
    assert digest_row("daily", "2026-11-03")["generated_at"] == first
    env.set(NOW + timedelta(minutes=61))
    out = actions(run(A.run_auto_digest()))
    assert out["daily"] == ("regenerate", "fallback:template")
    assert out["weekly"] == ("too_recent", "skipped") and out["monthly"] == ("too_recent", "skipped")  # < 24 jam
    row = digest_row("daily", "2026-11-03")
    assert row["generated_at"] > first and row["generated_trigger"] == "auto"
    assert "b" in json.loads(row["item_ids_json"])


def test_long_periods_regenerated_after_24_hours(env, monkeypatch):
    monkeypatch.setenv("INSIGHT_AUTO_LONG_MIN_HOURS", "24")
    seed(item("a"))
    run(A.run_auto_digest())
    later = NOW + timedelta(hours=25)              # 2026-11-04 11:00 WIB: bucket harian baru, minggu & bulan sama
    env.set(later)
    seed(item("c", score=90, published_at="2026-11-04T03:00:00Z", fetched_at="2026-11-04T03:30:00Z"))
    out = actions(run(A.run_auto_digest()))
    assert out == {"daily": ("create", "fallback:template"), "weekly": ("regenerate", "fallback:template"),
                   "monthly": ("regenerate", "fallback:template")}


def test_thresholds_configurable(env, monkeypatch):
    monkeypatch.setenv("INSIGHT_AUTO_DAILY_MIN_MINUTES", "5")
    monkeypatch.setenv("INSIGHT_GENERATE_COOLDOWN_SECONDS", "0")
    seed(item("a"))
    run(A.run_auto_digest())
    env.set(NOW + timedelta(minutes=6))
    seed(item("b", score=85, published_at="2026-11-03T03:02:00Z", fetched_at="2026-11-03T03:03:00Z"))
    assert actions(run(A.run_auto_digest()))["daily"][0] == "regenerate"


def test_regenerate_respects_existing_cooldown(env, monkeypatch):
    monkeypatch.setenv("INSIGHT_AUTO_DAILY_MIN_MINUTES", "0")
    monkeypatch.setenv("INSIGHT_GENERATE_COOLDOWN_SECONDS", "600")
    seed(item("a"))
    run(A.run_auto_digest())
    env.set(NOW + timedelta(minutes=1))
    seed(item("b", score=85, published_at="2026-11-03T03:00:30Z", fetched_at="2026-11-03T03:00:40Z"))
    assert actions(run(A.run_auto_digest()))["daily"] == ("regenerate", "cooldown")


def _valid_llm(monkeypatch, calls):
    async def fake(system, user, **kw):
        calls.append(1)
        data = json.loads(user.split(D.DATA_START, 1)[1].split(D.DATA_END, 1)[0])
        first = data["items"][0]["id"]
        return json.dumps({"executive_summary": "Ringkasan.", "key_events": [{"text": "Kejadian", "item_ids": [first]}],
                           "impact_note": "", "watchlist": []})

    monkeypatch.setattr(insight_llm, "available", lambda: True)
    monkeypatch.setattr(insight_llm, "complete", fake)


def test_llm_used_when_key_available(env, monkeypatch):
    calls = []
    _valid_llm(monkeypatch, calls)
    seed(item("a"))
    out = run(A.run_auto_digest())
    assert [r["result"] for r in out] == ["ready:llm"] * 3 and len(calls) == 3
    assert all(r["llm_called"] for r in out)


def test_daily_llm_call_limit(env, monkeypatch):
    monkeypatch.setenv("INSIGHT_AUTO_MAX_CALLS_PER_DAY", "2")
    monkeypatch.setenv("INSIGHT_AUTO_DAILY_MIN_MINUTES", "0")
    monkeypatch.setenv("INSIGHT_GENERATE_COOLDOWN_SECONDS", "0")
    calls = []
    _valid_llm(monkeypatch, calls)
    seed(item("a"))
    out = run(A.run_auto_digest())
    # 2 panggilan LLM pertama (daily, weekly); monthly baru dibuat dengan templat, tanpa LLM
    assert [(r["llm_called"], r["result"]) for r in out] == [
        (True, "ready:llm"), (True, "ready:llm"), (False, "fallback:template")]
    assert len(calls) == 2
    # brief stale: kuota habis → TIDAK menimpa brief LLM dengan templat
    env.set(NOW + timedelta(minutes=5))
    seed(item("b", score=85, published_at="2026-11-03T03:01:00Z", fetched_at="2026-11-03T03:02:00Z"))
    out = actions(run(A.run_auto_digest()))
    assert out["daily"] == ("regenerate", "llm_budget") and len(calls) == 2
    assert digest_row("daily", "2026-11-03")["generated_by"] == "llm"
    # hari WIB berikutnya: kuota baru
    env.set(utc(2026, 11, 3, 17, 30))               # 00:30 WIB 4 Nov
    seed(item("c", score=85, published_at="2026-11-03T17:00:00Z", fetched_at="2026-11-03T17:10:00Z"))
    assert actions(run(A.run_auto_digest()))["daily"] == ("create", "ready:llm") and len(calls) == 3


def test_auto_digest_switch_off(env, monkeypatch):
    monkeypatch.setenv("INSIGHT_AUTO_DIGEST", "off")
    seed(item("a"))
    assert run(A.run_auto_digest()) == []
    run(A.after_refresh({}))
    with dbm.session(get_settings().db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM insight_digests").fetchone()[0] == 0


def test_manual_generate_marked_manual_and_old_rows_default_manual(env):
    seed(item("a"))
    assert run(D.generate_digest("daily"))["generated_trigger"] == "manual"
    with dbm.session(get_settings().db_path) as conn:
        conn.execute("UPDATE insight_digests SET generated_trigger=NULL")   # baris sebelum Ronde 2
    assert D.get_digest("daily")["generated_trigger"] == "manual"
    assert D.not_generated("daily", "id", True)["generated_trigger"] is None


def test_schema_migration_adds_column_to_old_table(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(dbm.SCHEMA.split("-- Ronde 2")[0])     # skema Ronde 1
    conn.close()
    dbm.init_schema(path)
    dbm.init_schema(path)                                      # idempoten
    with dbm.session(path) as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(insight_digests)")}
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "generated_trigger" in cols and {"insight_source_health", "insight_auto_digest_log"} <= tables


# ---------- pemicu pasca-refresh ----------

class FakeAdapter:
    def __init__(self, name, items=(), slow=False, delay=0.0):
        self.name, self.label, self.attribution = name, name, f"Sumber: {name}"
        self._items, self.slow, self._delay = list(items), slow, delay

    async def fetch(self, client):
        if self._delay:
            await asyncio.sleep(self._delay)
        return list(self._items)


def raw(source, title, url):
    return RawItem(source=source, source_label=source, attribution=f"Sumber: {source}", title=title, url=url,
                   published_at=utc(2026, 11, 3, 2))


def test_hooks_run_after_refresh_isolated(env, no_hooks):
    seen = []

    def boom(result):
        raise RuntimeError("rusak")

    async def good(result):
        seen.append([r["source"] for r in result["results"]])

    pipeline.register_after_refresh(boom)
    pipeline.register_after_refresh(good)
    pipeline.register_after_refresh(good)          # idempoten

    async def go():
        res = await pipeline.refresh(get_settings(), adapters=[FakeAdapter("bmkg_quake")])
        assert seen == []                          # pemicu tidak ditunggu oleh refresh
        await pipeline.wait_background()
        return res

    res = run(go())
    assert res["results"][0]["ok"] is True
    assert seen == [["bmkg_quake"]]
    assert run(pipeline.run_after_refresh({"results": []})) == [f"{boom.__qualname__}: RuntimeError"]


def test_slow_sources_deferred_then_hooks_get_full_result(env, no_hooks):
    seen = []
    pipeline.register_after_refresh(lambda r: seen.append({x["source"]: x for x in r["results"]}))
    fast = FakeAdapter("bmkg_quake", [raw("bmkg_quake", "Gempa M5", "https://b.example/1")])
    slow = FakeAdapter("gdelt", [raw("gdelt", "IHSG anjlok", "https://g.example/1")], slow=True, delay=0.2)

    async def go():
        t0 = time.monotonic()
        res = await pipeline.refresh(get_settings(), adapters=[fast, slow], defer_slow=True)
        elapsed = time.monotonic() - t0
        assert not pipeline.is_running()           # lock utama sudah dilepas
        await pipeline.wait_background()
        return res, elapsed

    res, elapsed = run(go())
    by = {r["source"]: r for r in res["results"]}
    assert elapsed < 0.2
    assert by["bmkg_quake"]["new_items"] == 1 and not by["bmkg_quake"].get("background")
    assert by["gdelt"] == {"source": "gdelt", "ok": True, "new_items": 0, "error": None, "background": True}
    assert seen and seen[0]["gdelt"]["new_items"] == 1 and seen[0]["bmkg_quake"]["new_items"] == 1
    with dbm.session(get_settings().db_path) as conn:
        assert conn.execute("SELECT category FROM insight_items WHERE source='gdelt'").fetchone()[0] == "pasar_keuangan"


def test_defer_slow_off_keeps_old_behaviour(env, no_hooks):
    slow = FakeAdapter("gdelt", [raw("gdelt", "Banjir", "https://g.example/2")], slow=True)
    res = run(pipeline.refresh(get_settings(), adapters=[slow]))
    assert res["results"] == [{"source": "gdelt", "ok": True, "new_items": 1, "error": None, "degraded": False}]


def test_slow_sources_never_run_twice(env, no_hooks):
    calls = []

    class Slow(FakeAdapter):
        async def fetch(self, client):
            calls.append(1)
            await asyncio.sleep(0.2)
            return []

    async def go():
        await pipeline.refresh(get_settings(), adapters=[Slow("gdelt", slow=True)], defer_slow=True)
        await asyncio.sleep(0.02)
        await pipeline.refresh(get_settings(), adapters=[Slow("gdelt", slow=True)], defer_slow=True)
        await pipeline.wait_background()

    run(go())
    assert calls == [1]


def test_refresh_triggers_auto_digest_end_to_end(env, no_hooks):
    from insight import auto_digest
    pipeline.register_after_refresh(auto_digest.after_refresh)
    a = FakeAdapter("bmkg_quake", [raw("bmkg_quake", "Gempa M6 di Papua", "https://b.example/9")])

    async def go():
        await pipeline.refresh(get_settings(), adapters=[a], defer_slow=True)
        await pipeline.wait_background()

    run(go())
    d = D.get_digest("daily")
    assert d["status"] == "fallback" and d["generated_trigger"] == "auto" and len(d["items"]) == 1


def test_post_refresh_defers_slow_and_returns_fast(env, no_hooks, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from insight import setup_insight
    from polaris_auth import setup_auth

    monkeypatch.setenv("INSIGHT_SOURCES", "bmkg_quake,gdelt")
    monkeypatch.setenv("INSIGHT_AUTO_DIGEST", "off")
    started = []

    class Gdelt(FakeAdapter):
        async def fetch(self, client):
            started.append(1)
            await asyncio.sleep(0.5)
            return []

    monkeypatch.setattr(pipeline, "build_adapters", lambda s: [FakeAdapter("bmkg_quake"), Gdelt("gdelt", slow=True)])
    app = FastAPI()
    setup_auth(app)
    setup_insight(app)
    service.create_user("admin1", "Sangat-Kuat-2026", "admin")
    H = {"X-Requested-With": "polarisbi"}
    with TestClient(app, base_url="http://testserver") as c:
        assert c.post("/auth/login", json={"username": "admin1", "password": "Sangat-Kuat-2026"}, headers=H).status_code == 200
        t0 = time.monotonic()
        r = c.post("/api/insight/refresh", headers=H)
        elapsed = time.monotonic() - t0
    assert r.status_code == 200 and elapsed < 0.5
    by = {x["source"]: x for x in r.json()["results"]}
    assert by["gdelt"]["background"] is True and by["bmkg_quake"]["background"] is False
    ev = [e for e in service.audit_entries(20) if e["event"] == "insight_refresh"]
    assert "gdelt:background:0" in ev[0]["detail"]


# ---------- scheduler ----------

def test_scheduler_on_by_default(monkeypatch):
    monkeypatch.delenv("INSIGHT_SCHEDULER", raising=False)
    s = get_settings()
    assert s.scheduler is True and s.scheduler_startup_delay == 10.0 and s.auto_digest is True
    assert (s.auto_daily_min_minutes, s.auto_long_min_hours, s.auto_max_calls_per_day) == (60, 24, 30)


def test_scheduler_first_refresh_after_startup_delay_in_background(insight_env, monkeypatch):
    calls = []

    async def fake_refresh(*a, **k):
        calls.append((time.monotonic(), k))
        return {"results": [], "finished_at": "x"}

    monkeypatch.setattr(pipeline, "refresh", fake_refresh)

    async def go():
        sch = InsightScheduler(interval_seconds=60, startup_delay=0.15)
        t0 = time.monotonic()
        sch.start()                                 # tidak memblokir startup
        assert time.monotonic() - t0 < 0.05 and calls == []
        await asyncio.sleep(0.05)
        assert calls == []                          # belum lewat jeda awal
        await asyncio.sleep(0.25)
        await sch.stop()
        return t0

    t0 = run(go())
    assert len(calls) == 1 and calls[0][0] - t0 >= 0.15 and calls[0][1] == {"defer_slow": True}


def test_scheduler_skips_cycle_when_refresh_already_running(insight_env, monkeypatch):
    calls = []

    async def busy(*a, **k):
        calls.append(1)
        raise pipeline.AlreadyRunning()

    monkeypatch.setattr(pipeline, "refresh", busy)

    async def go():
        sch = InsightScheduler(interval_seconds=0.05, startup_delay=0)
        sch.start()
        await asyncio.sleep(0.2)
        assert sch.running                          # AlreadyRunning tidak menghentikan loop
        await sch.stop()

    run(go())
    assert len(calls) >= 2


def test_scheduler_stop_during_startup_delay(insight_env, monkeypatch):
    calls = []

    async def fake_refresh(*a, **k):
        calls.append(1)

    monkeypatch.setattr(pipeline, "refresh", fake_refresh)

    async def go():
        sch = InsightScheduler(startup_delay=10)
        sch.start()
        await asyncio.sleep(0.05)
        await sch.stop()
        assert not sch.running

    run(go())
    assert calls == []
