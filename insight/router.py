"""Endpoint /api/insight/* (dilindungi AuthMiddleware karena berawalan /api)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request

from polaris_auth import require_role, require_user
from polaris_auth.deps import client_ip, csrf_guard

from . import db as dbm
from . import digest as digest_mod
from . import pipeline
from .config import get_settings
from .exposure import get_provider
from .models import (CATEGORIES, DigestResponse, ExposureResponse, FeedResponse, GenerateRequest, InsightError,
                     RefreshResponse, SourceStatus)
from .provinces import canonical
from .sources import BUILTIN_META

log = logging.getLogger("insight")

router = APIRouter(prefix="/api/insight", tags=["insight"],
                   dependencies=[Depends(csrf_guard), Depends(require_user)])

FEED_DEFAULT_LIMIT = 50
FEED_MAX_LIMIT = 200


def _audit(request: Request, user: dict, event: str, detail: str) -> None:
    """Catat ke audit_log polaris_auth lewat fungsi publik service.audit (tanpa mengubah polaris_auth)."""
    try:
        from polaris_auth import db as auth_db, service as auth_service
        from polaris_auth.config import get_settings as auth_settings

        with auth_db.session(auth_settings().db_path) as conn:
            auth_service.audit(conn, event, user_id=user.get("id"), username=user.get("username"),
                               ip=client_ip(request), detail=detail)
    except Exception as e:  # audit tidak boleh menggagalkan aksi
        log.warning("insight: gagal menulis audit %s: %s", event, type(e).__name__)


@router.get("/feed", response_model=FeedResponse)
def feed(category: Optional[str] = Query(None), province: Optional[str] = Query(None),
         min_score: Optional[int] = Query(None), since: Optional[str] = Query(None),
         limit: int = Query(FEED_DEFAULT_LIMIT), offset: int = Query(0)):
    s = get_settings()
    where, args = [], []
    if category:
        if category not in CATEGORIES:
            raise InsightError(422, "invalid_category", "Kategori tidak dikenal.")
        where.append("category=?")
        args.append(category)
    if province:
        prov = canonical(province)
        if prov is None:
            raise InsightError(422, "invalid_province", "Provinsi tidak dikenal.")
        where.append("province=?")
        args.append(prov)
    if min_score is not None:
        where.append("score>=?")
        args.append(max(0, min(100, min_score)))
    if since:
        dt = dbm.parse_iso(since)
        if dt is None:
            raise InsightError(422, "invalid_since", "since harus ISO 8601.")
        where.append("published_at>=?")
        args.append(dbm.to_iso(dt))
    limit = max(1, min(FEED_MAX_LIMIT, limit))
    offset = max(0, offset)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    with dbm.session(s.db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM insight_items{clause}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM insight_items{clause} ORDER BY score DESC, published_at DESC, id ASC LIMIT ? OFFSET ?",
            [*args, limit, offset]).fetchall()
    return {"items": [digest_mod.row_to_feed(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/digest", response_model=DigestResponse)
def get_digest(period: Optional[str] = Query(None)):
    return digest_mod.get_digest(period, "id")


@router.post("/digest/generate", response_model=DigestResponse)
async def generate_digest(request: Request, body: GenerateRequest = Body(default_factory=GenerateRequest),
                          user: dict = Depends(require_role("analyst", "admin"))):
    detail = f"period={body.period} force={body.force}"
    try:
        result = await digest_mod.generate_digest(body.period, force=body.force, language=body.language)
    except InsightError as e:
        _audit(request, user, "insight_digest_generate", f"{detail} result={e.code}")
        raise
    _audit(request, user, "insight_digest_generate",
           f"{detail} bucket={result['bucket_key']} status={result['status']} by={result['generated_by']}")
    return result


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, user: dict = Depends(require_role("admin"))):
    try:
        # sumber lambat (GDELT, Kemenkes) dilanjutkan di latar belakang agar respons < 60 detik
        result = await pipeline.refresh(defer_slow=True)
    except pipeline.AlreadyRunning:
        _audit(request, user, "insight_refresh", "result=already_running")
        raise InsightError(409, "already_running", "Refresh sedang berjalan.") from None

    def _state(r: dict) -> str:
        if r.get("background"):
            return "background"
        if not r["ok"]:
            return "error"
        return "degraded" if r.get("degraded") else "ok"

    summary = ",".join(f"{r['source']}:{_state(r)}:{r['new_items']}" for r in result["results"])
    _audit(request, user, "insight_refresh", f"result={summary}"[:500])
    return result


@router.get("/sources", response_model=list[SourceStatus])
def sources():
    s = get_settings()
    enabled = set(s.enabled_keys)
    catalog: list[tuple[str, str, str]] = [(k, lbl, attr) for k, (lbl, attr) in BUILTIN_META.items()]
    catalog += [(f.key, f.label, f"Sumber: {f.label}") for f in s.rss_feeds]
    with dbm.session(s.db_path) as conn:
        status_rows = {r["source"]: r for r in conn.execute("SELECT * FROM insight_source_status")}
        health = {r["source"]: r for r in conn.execute("SELECT * FROM insight_source_health")}
    stale_after = timedelta(minutes=3 * s.refresh_minutes)
    now = dbm.utcnow()
    out = []
    for key, label, attribution in catalog:
        r = status_rows.get(key)
        last_attempt = r["last_attempt_at"] if r else None
        last_success = r["last_success_at"] if r else None
        last_error = r["last_error"] if r else None
        if key not in enabled:
            status = "disabled"
        elif last_error and (not last_success or (last_attempt or "") > last_success):
            status = "error"
        elif not last_success or now - dbm.parse_iso(last_success) > stale_after:
            status = "stale"
        else:
            status = "ok"
        out.append({"source": key, "label": label, "attribution": attribution, "enabled": key in enabled,
                    "status": status, "last_attempt_at": last_attempt, "last_success_at": last_success,
                    "last_item_count": r["last_item_count"] if r else None, "last_error": last_error,
                    "degraded": bool(health[key]["degraded"]) if key in health else False,
                    "degraded_reason": health[key]["degraded_reason"] if key in health else None})
    return out


@router.get("/exposure", response_model=ExposureResponse)
def exposure():
    provider = get_provider()
    rows = sorted(provider.get_exposure(None), key=lambda r: (r["province"], r["product"]))
    return {"is_demo": bool(provider.is_demo), "rows": rows}


__all__ = ["router"]
