"""Ringkasan otomatis setelah tiap siklus refresh (dipasang lewat pipeline.register_after_refresh).

Urutan sekuensial: daily → weekly → monthly. Aturan per periode (bucket WIB saat ini):
1. Tidak ada kejadian pada jendela periode itu            → lewati ("no_events").
2. Belum ada brief untuk bucket ini                         → buat ("create").
3. Brief ada, is_stale, dan umurnya >= ambang               → buat ulang ("regenerate", force=True).
   Ambang: daily INSIGHT_AUTO_DAILY_MIN_MINUTES (60), weekly & monthly INSIGHT_AUTO_LONG_MIN_HOURS (24).
4. Selain itu                                               → lewati ("fresh" / "too_recent").

LLM dipakai bila kunci API ada DAN panggilan LLM otomatis hari ini (hari WIB) < INSIGHT_AUTO_MAX_CALLS_PER_DAY.
Bila batas tercapai: brief BARU tetap dibuat dengan templat; brief lama TIDAK ditimpa templat ("llm_budget").
Cooldown & lock anti-duplikat memakai yang sama dengan endpoint manual (digest.generate_digest).
Setiap pembuatan dicatat ke insight_auto_digest_log dan audit_log (event insight_digest_auto, actor system).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import db as dbm
from . import digest as D
from . import llm as insight_llm
from .config import InsightSettings, get_settings
from .models import PERIODS, InsightError

log = logging.getLogger("insight")

AUDIT_EVENT = "insight_digest_auto"
SYSTEM_ACTOR = "system"
LANGUAGE = "id"


def min_age(period: str, s: InsightSettings) -> timedelta:
    if period == "daily":
        return timedelta(minutes=s.auto_daily_min_minutes)
    return timedelta(hours=s.auto_long_min_hours)


def wib_day_start_utc(now: datetime) -> datetime:
    local = now.astimezone(D.WIB)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def llm_calls_today(conn, now: datetime) -> int:
    since = dbm.to_iso(wib_day_start_utc(now))
    return conn.execute("SELECT COUNT(*) FROM insight_auto_digest_log WHERE llm_called=1 AND at >= ?",
                        (since,)).fetchone()[0]


def decide(conn, period: str, now: datetime, s: InsightSettings) -> str:
    """Kembalikan "create", "regenerate", atau alasan lewati ("no_events", "fresh", "too_recent")."""
    start, end = D.window(period, now)
    if D.count_items(conn, start, end) == 0:
        return "no_events"
    row = conn.execute("SELECT * FROM insight_digests WHERE period=? AND bucket_key=? AND language=?",
                       (period, D.bucket_key(period, now), LANGUAGE)).fetchone()
    if row is None:
        return "create"
    if not D.compute_is_stale(conn, row):
        return "fresh"
    generated = dbm.parse_iso(row["generated_at"])
    if generated is not None and now - generated < min_age(period, s):
        return "too_recent"
    return "regenerate"


def _audit(detail: str) -> None:
    try:
        from polaris_auth import db as auth_db, service as auth_service
        from polaris_auth.config import get_settings as auth_settings

        with auth_db.session(auth_settings().db_path) as conn:
            auth_service.audit(conn, AUDIT_EVENT, user_id=None, username=SYSTEM_ACTOR, ip=None, detail=detail)
    except Exception as e:  # audit tidak boleh menggagalkan ringkasan otomatis
        log.warning("insight: gagal menulis audit %s: %s", AUDIT_EVENT, type(e).__name__)


def _log(s: InsightSettings, at: datetime, period: str, key: str, action: str, llm_called: bool, result: str) -> None:
    with dbm.session(s.db_path) as conn:
        conn.execute("INSERT INTO insight_auto_digest_log(at,period,bucket_key,action,llm_called,result)"
                     " VALUES (?,?,?,?,?,?)", (dbm.to_iso(at), period, key, action, 1 if llm_called else 0,
                                                result[:200]))


async def run_auto_digest(settings: InsightSettings | None = None) -> list[dict]:
    """Jalankan aturan auto-digest untuk ketiga periode. Mengembalikan keputusan per periode (untuk tes/log)."""
    s = settings or get_settings()
    if not s.auto_digest:
        return []
    dbm.init_schema(s.db_path)
    out: list[dict] = []
    for period in PERIODS:   # sekuensial: daily, weekly, monthly
        now = dbm.utcnow()
        key = D.bucket_key(period, now)
        with dbm.session(s.db_path) as conn:
            action = decide(conn, period, now, s)
            used = llm_calls_today(conn, now)
        entry = {"period": period, "bucket_key": key, "action": action, "llm_called": False, "result": "skipped"}
        if action not in ("create", "regenerate"):
            out.append(entry)
            continue
        budget_ok = used < s.auto_max_calls_per_day
        if not budget_ok and action == "regenerate":
            entry["result"] = "llm_budget"   # jangan timpa brief yang ada dengan templat
            out.append(entry)
            continue
        use_llm = budget_ok and insight_llm.available()
        stats: dict = {}
        try:
            res = await D.generate_digest(period, force=(action == "regenerate"), language=LANGUAGE, settings=s,
                                          trigger="auto", use_llm=use_llm, stats=stats)
            entry["result"] = f"{res['status']}:{res['generated_by']}" if stats.get("generated") else "existing"
        except InsightError as e:      # cooldown (429) / sedang dibuat (409)
            entry["result"] = e.code
        except Exception as e:         # pemicu tidak boleh menggagalkan siklus berikutnya
            entry["result"] = f"error:{type(e).__name__}"
            log.warning("insight auto-digest %s gagal (%s)", period, type(e).__name__)
        entry["llm_called"] = bool(stats.get("llm_called"))
        _log(s, now, period, key, action, entry["llm_called"], entry["result"])
        _audit(f"period={period} bucket={key} action={action} result={entry['result']} "
               f"llm_called={int(entry['llm_called'])} llm_calls_today={used + int(entry['llm_called'])}")
        out.append(entry)
    return out


async def after_refresh(_result: dict) -> None:
    """Callback untuk pipeline.register_after_refresh. Saklar dibaca saat dipanggil (INSIGHT_AUTO_DIGEST)."""
    if get_settings().auto_digest:
        await run_auto_digest()
