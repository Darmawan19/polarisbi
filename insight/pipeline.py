"""Pipeline refresh: fetch paralel → bersihkan → klasifikasi & skor → simpan → dedupe → retensi."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta

import httpx

from . import db as dbm
from . import scoring_rules as R
from .classify import (SNIPPET_MAX, TITLE_MAX, classify_and_score, clean_text, clean_url, looks_like_injection,
                       normalize_title)
from .config import USER_AGENT, InsightSettings, get_settings
from .models import RawItem, SourceError
from .sources import SourceAdapter, build_adapters

log = logging.getLogger("insight")

REFRESH_DEADLINE_SECONDS = 60.0
_refresh_lock = threading.Lock()   # lintas event loop/thread; dipakai non-blocking


class AlreadyRunning(Exception):
    pass


def is_running() -> bool:
    return _refresh_lock.locked()


def make_client(settings: InsightSettings) -> httpx.AsyncClient:
    """Dipisah supaya tes bisa menggantinya dengan httpx.MockTransport."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        max_redirects=3,
    )


def item_id(source: str, url: str) -> str:
    return hashlib.sha256(f"{source}|{url}".encode("utf-8")).hexdigest()[:32]


def prepare(raw: RawItem, fetched_at: datetime) -> dict | None:
    """RawItem → baris DB yang sudah bersih. None bila item ditolak."""
    url = clean_url(raw.url)
    title = clean_text(raw.title, TITLE_MAX)
    if not url or not title:
        return None
    snippet = clean_text(raw.snippet, SNIPPET_MAX)
    category, province, score = classify_and_score(
        raw.source, title, snippet, raw.meta, preset_category=raw.category, preset_province=raw.province,
    )
    meta = {k: v for k, v in (raw.meta or {}).items() if isinstance(v, (str, int, float, bool, type(None)))}
    if looks_like_injection(f"{title}\n{snippet}"):
        meta["suspicious"] = True   # dikecualikan dari masukan LLM di digest
    base = raw.source.split(".", 1)[0]
    published = raw.published_at or fetched_at
    return {
        "id": item_id(raw.source, url),
        "source": raw.source,
        "source_label": clean_text(raw.source_label, 100),
        "attribution": clean_text(raw.attribution, 100),
        "title": title,
        "snippet": snippet,
        "url": url,
        "published_at": dbm.to_iso(published),
        "fetched_at": dbm.to_iso(fetched_at),
        "category": category,
        "province": province,
        "score": int(score),
        "severity_verified": 1 if raw.severity_verified else 0,
        "dedupe_key": None if base in R.TITLE_DEDUPE_EXCLUDED_SOURCES else (
            hashlib.sha1(normalize_title(title).encode("utf-8")).hexdigest()[:20]),
        "meta_json": json.dumps(meta, ensure_ascii=False)[:4000],
    }


def store_items(conn, rows: list[dict]) -> int:
    """Upsert. fetched_at tetap = waktu pertama terlihat. Mengembalikan jumlah item baru."""
    new = 0
    with dbm.tx(conn):
        for r in rows:
            exists = conn.execute("SELECT 1 FROM insight_items WHERE id=?", (r["id"],)).fetchone()
            if exists:
                conn.execute(
                    "UPDATE insight_items SET title=?, snippet=?, published_at=?, category=?, province=?, score=?,"
                    " severity_verified=?, dedupe_key=?, meta_json=?, source_label=?, attribution=? WHERE id=?",
                    (r["title"], r["snippet"], r["published_at"], r["category"], r["province"], r["score"],
                     r["severity_verified"], r["dedupe_key"], r["meta_json"], r["source_label"],
                     r["attribution"], r["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO insight_items(id,source,source_label,attribution,title,snippet,url,published_at,"
                    "fetched_at,category,province,score,severity_verified,dedupe_key,meta_json)"
                    " VALUES (:id,:source,:source_label,:attribution,:title,:snippet,:url,:published_at,"
                    ":fetched_at,:category,:province,:score,:severity_verified,:dedupe_key,:meta_json)", r,
                )
                new += 1
    return new


def dedupe_titles(conn) -> int:
    """Judul ternormalisasi sama, lintas sumber, dalam 48 jam → simpan skor tertinggi."""
    keys = [r[0] for r in conn.execute(
        "SELECT dedupe_key FROM insight_items WHERE dedupe_key IS NOT NULL"
        " GROUP BY dedupe_key HAVING COUNT(*) > 1").fetchall()]
    window = timedelta(hours=R.DEDUPE_WINDOW_HOURS)
    removed: list[str] = []
    for key in keys:
        rows = conn.execute(
            "SELECT id, score, published_at, fetched_at FROM insight_items WHERE dedupe_key=?"
            " ORDER BY score DESC, fetched_at ASC, id ASC", (key,)).fetchall()
        kept: list[tuple[str, datetime]] = []
        for r in rows:
            pub = dbm.parse_iso(r["published_at"])
            if any(abs(pub - kp) <= window for _, kp in kept):
                removed.append(r["id"])
            else:
                kept.append((r["id"], pub))
    if removed:
        with dbm.tx(conn):
            conn.executemany("DELETE FROM insight_items WHERE id=?", [(i,) for i in removed])
    return len(removed)


def purge_old(conn, settings: InsightSettings, now: datetime) -> int:
    cutoff = dbm.to_iso(now - timedelta(days=settings.retention_days))
    with dbm.tx(conn):
        n = conn.execute("DELETE FROM insight_items WHERE published_at < ?", (cutoff,)).rowcount
        conn.execute("DELETE FROM insight_cap_cache WHERE fetched_at < ?", (cutoff,))
    return n


def _record_status(conn, source: str, *, attempt: str, ok: bool, count: int | None, error: str | None) -> None:
    conn.execute(
        "INSERT INTO insight_source_status(source,enabled,last_attempt_at,last_success_at,last_item_count,last_error)"
        " VALUES (?,1,?,?,?,?) ON CONFLICT(source) DO UPDATE SET enabled=1, last_attempt_at=excluded.last_attempt_at,"
        " last_success_at=COALESCE(excluded.last_success_at, insight_source_status.last_success_at),"
        " last_item_count=COALESCE(excluded.last_item_count, insight_source_status.last_item_count),"
        " last_error=excluded.last_error",
        (source, attempt, attempt if ok else None, count if ok else None, None if ok else (error or "error")[:300]),
    )


def _safe_error(e: BaseException) -> str:
    if isinstance(e, SourceError):
        return str(e)[:300]
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    return f"kesalahan internal: {type(e).__name__}"


async def _run_refresh(settings: InsightSettings, adapters: list[SourceAdapter], deadline: float) -> list[dict]:
    started = dbm.utcnow()
    attempt_iso = dbm.to_iso(started)
    results: dict[str, dict] = {}
    async with make_client(settings) as client:
        tasks = {asyncio.ensure_future(a.fetch(client)): a for a in adapters}
        done, pending = await asyncio.wait(tasks, timeout=deadline) if tasks else (set(), set())
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    fetched_at = dbm.utcnow()
    with dbm.session(settings.db_path) as conn:
        for task, adapter in tasks.items():
            if task in pending:
                err = f"melewati batas waktu refresh {int(deadline)} detik"
                results[adapter.name] = {"source": adapter.name, "ok": False, "new_items": 0, "error": err}
                _record_status(conn, adapter.name, attempt=attempt_iso, ok=False, count=None, error=err)
                continue
            exc = task.exception()
            if exc is not None:
                err = _safe_error(exc)
                if not isinstance(exc, SourceError):
                    log.warning("insight source %s gagal: %s", adapter.name, type(exc).__name__)
                results[adapter.name] = {"source": adapter.name, "ok": False, "new_items": 0, "error": err}
                _record_status(conn, adapter.name, attempt=attempt_iso, ok=False, count=None, error=err)
                continue
            rows = [r for r in (prepare(raw, fetched_at) for raw in task.result()) if r]
            # duplikat id dalam satu batch: simpan skor tertinggi
            by_id: dict[str, dict] = {}
            for r in rows:
                if r["id"] not in by_id or r["score"] > by_id[r["id"]]["score"]:
                    by_id[r["id"]] = r
            new = store_items(conn, list(by_id.values()))
            results[adapter.name] = {"source": adapter.name, "ok": True, "new_items": new, "error": None}
            _record_status(conn, adapter.name, attempt=attempt_iso, ok=True, count=len(by_id), error=None)
        dedupe_titles(conn)
        purge_old(conn, settings, fetched_at)
    return [results[a.name] for a in adapters]


async def refresh(settings: InsightSettings | None = None, *, adapters: list[SourceAdapter] | None = None,
                  deadline: float = REFRESH_DEADLINE_SECONDS) -> dict:
    """Refresh semua sumber aktif. Lempar AlreadyRunning bila refresh lain sedang berjalan."""
    s = settings or get_settings()
    if not _refresh_lock.acquire(blocking=False):
        raise AlreadyRunning()
    try:
        dbm.init_schema(s.db_path)
        results = await _run_refresh(s, adapters if adapters is not None else build_adapters(s), deadline)
        return {"results": results, "finished_at": dbm.to_iso(dbm.utcnow())}
    finally:
        _refresh_lock.release()
