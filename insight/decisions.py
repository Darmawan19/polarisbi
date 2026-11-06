"""Log keputusan: menyimpan keputusan aktif (upsert tanpa menimpa status) dan perubahan status oleh manusia.

- Keputusan aktif disimpan setiap kali mesin keputusan menghasilkan hitungan baru (bukan dari cache):
  a. lewat pemicu pasca-refresh yang sudah ada (pipeline.register_after_refresh, callback terisolasi), dan
  b. secara malas saat GET overview / detail produk pertama kali menghitung (overview.on_compute).
  Sumber lambat (GDELT, Kemenkes) selesai di latar belakang hingga ~47 detik setelah refresh dan pemicu berjalan
  sesudahnya, jadi keputusan bisa sedikit terlambat dibanding berita cepat.
- Upsert hanya memperbarui rule_id, last_seen_at, last_level, last_title. Status, catatan, updated_by, dan
  updated_at hanya berubah lewat set_status. Keputusan yang tidak lagi aktif tetap ada (last_seen_at lama).
- insight_decision_event append-only: satu baris saat keputusan pertama terlihat (actor "system", ke "baru") dan
  satu baris per perubahan status.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from . import db as dbm
from .config import InsightSettings, get_settings

log = logging.getLogger("insight")

STATUSES = ("baru", "ditinjau", "disetujui", "ditunda", "ditolak")
DEFAULT_STATUS = "baru"
NOTE_MAX = 500
SYSTEM_ACTOR = "system"
HISTORY_DEFAULT_LIMIT = 50
HISTORY_MAX_LIMIT = 200


def upsert_active(conn, decisions: list[dict], now: datetime) -> int:
    """Simpan keputusan aktif. Tidak pernah menimpa status. Mengembalikan jumlah keputusan baru."""
    at = dbm.to_iso(now)
    new = 0
    with dbm.tx(conn):
        for d in decisions:
            cur = conn.execute(
                "INSERT OR IGNORE INTO insight_decision(key,rule_id,first_seen_at,last_seen_at,last_level,last_title,"
                "status) VALUES (?,?,?,?,?,?,?)",
                (d["key"], d["rule_id"], at, at, d["level"], d["title"][:300], DEFAULT_STATUS))
            if cur.rowcount:
                new += 1
                conn.execute("INSERT INTO insight_decision_event(key,dari_status,ke_status,note,actor,at)"
                             " VALUES (?,?,?,?,?,?)", (d["key"], None, DEFAULT_STATUS, None, SYSTEM_ACTOR, at))
            else:
                conn.execute(
                    "UPDATE insight_decision SET rule_id=?, last_level=?, last_title=?,"
                    " last_seen_at=MAX(last_seen_at, ?) WHERE key=?",
                    (d["rule_id"], d["level"], d["title"][:300], at, d["key"]))
    return new


def status_map(conn, keys: list[str]) -> dict[str, dict]:
    if not keys:
        return {}
    rows = conn.execute("SELECT * FROM insight_decision WHERE key IN (%s)" % ",".join("?" * len(keys)),
                        keys).fetchall()
    return {r["key"]: dict(r) for r in rows}


def merge_status(decisions: list[dict], smap: dict[str, dict]) -> list[dict]:
    """Salinan keputusan + status dari log (bagian ini tidak pernah di-cache)."""
    out = []
    for d in decisions:
        row = smap.get(d["key"])
        out.append({**d,
                    "status": row["status"] if row else DEFAULT_STATUS,
                    "status_note": row["note"] if row else None,
                    "status_updated_at": row["updated_at"] if row else None,
                    "status_updated_by": row["updated_by"] if row else None,
                    "first_seen_at": row["first_seen_at"] if row else None})
    return out


def _events(conn, keys: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {k: [] for k in keys}
    if not keys:
        return out
    for r in conn.execute("SELECT key, dari_status, ke_status, note, actor, at FROM insight_decision_event"
                          " WHERE key IN (%s) ORDER BY id ASC" % ",".join("?" * len(keys)), keys):
        out[r["key"]].append({k: r[k] for k in ("dari_status", "ke_status", "note", "actor", "at")})
    return out


def get_decision(conn, key: str) -> dict | None:
    row = conn.execute("SELECT * FROM insight_decision WHERE key=?", (key,)).fetchone()
    if row is None:
        return None
    return {**dict(row), "events": _events(conn, [key])[key]}


def set_status(conn, key: str, status: str, note: str | None, actor: str, now: datetime) -> dict | None:
    """Ubah status (status sudah divalidasi pemanggil). None bila key tidak dikenal."""
    at = dbm.to_iso(now)
    with dbm.tx(conn):
        row = conn.execute("SELECT status FROM insight_decision WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE insight_decision SET status=?, note=?, updated_by=?, updated_at=? WHERE key=?",
                     (status, note, actor, at, key))
        conn.execute("INSERT INTO insight_decision_event(key,dari_status,ke_status,note,actor,at)"
                     " VALUES (?,?,?,?,?,?)", (key, row["status"], status, note, actor, at))
    return get_decision(conn, key)


def history(conn, limit: int = HISTORY_DEFAULT_LIMIT) -> list[dict]:
    limit = max(1, min(HISTORY_MAX_LIMIT, int(limit)))
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM insight_decision ORDER BY last_seen_at DESC, first_seen_at DESC, key ASC LIMIT ?", (limit,))]
    ev = _events(conn, [r["key"] for r in rows])
    return [{**r, "events": ev[r["key"]]} for r in rows]


# ---------- penyimpanan otomatis ----------

def persist_engine(engine, settings: InsightSettings) -> None:
    """overview.on_compute: simpan keputusan aktif dari hitungan baru. Tidak boleh menggagalkan overview."""
    try:
        with dbm.session(settings.db_path) as conn:
            upsert_active(conn, engine.decisions, engine.signals.now)
    except Exception as e:
        log.warning("insight: gagal menyimpan log keputusan (%s)", type(e).__name__)


def _refresh_sync() -> None:
    from . import overview

    s = get_settings()
    overview.invalidate()
    engine = overview.compute(s, use_cache=False)
    persist_engine(engine, s)   # idempoten; aman walau on_compute juga terdaftar


async def after_refresh(_result: dict) -> None:
    """Callback pipeline.register_after_refresh: hitung ulang mesin keputusan dan simpan keputusan aktif."""
    await asyncio.to_thread(_refresh_sync)
