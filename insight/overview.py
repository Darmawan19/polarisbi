"""Rangkaian mesin keputusan: sinyal → peta panas produk → keputusan, plus cache hasil hitung.

Hasil hitung di-cache CACHE_TTL_SECONDS per penanda data (waktu refresh terakhir, jumlah & waktu item terbaru)
dan per ember waktu CACHE_TTL_SECONDS. Status keputusan dari log TIDAK ikut cache (digabung di router).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from . import db as dbm
from . import playbook as PB
from . import products as P
from . import signals as S
from .config import InsightSettings, get_settings

CACHE_TTL_SECONDS = 30.0

_cache: dict[tuple, tuple[float, "Engine"]] = {}
_lock = threading.Lock()
# dipanggil sekali per hasil hitung baru (tidak dari cache), mis. untuk menyimpan keputusan aktif ke log
_on_compute: list[Callable[["Engine", InsightSettings], None]] = []


@dataclass
class Engine:
    signals: S.Signals
    matrix: list[dict]
    decisions: list[dict]
    headline: str
    product_data_is_demo: bool
    provider: P.ProductExposureProvider


def on_compute(callback: Callable[[Engine, InsightSettings], None]) -> None:
    if callback not in _on_compute:
        _on_compute.append(callback)


def invalidate() -> None:
    with _lock:
        _cache.clear()


def _marker(conn) -> tuple:
    a = conn.execute("SELECT MAX(last_attempt_at) FROM insight_source_status").fetchone()[0]
    n, f, p = conn.execute("SELECT COUNT(*), MAX(fetched_at), MAX(published_at) FROM insight_items").fetchone()
    return (a, n, f, p)


def compute(settings: InsightSettings | None = None, now: datetime | None = None, *,
            use_cache: bool = True) -> Engine:
    s = settings or get_settings()
    now = now or dbm.utcnow()
    dbm.init_schema(s.db_path)
    with dbm.session(s.db_path) as conn:
        key = (str(s.db_path), s.product_provider, str(s.product_csv), str(s.product_province_csv),
               _marker(conn), int(now.timestamp() // CACHE_TTL_SECONDS))
        if use_cache:
            with _lock:
                hit = _cache.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
        sig = S.compute_signals(conn, now)
    provider = P.get_product_provider(s)
    matrix = P.heat_matrix(sig, provider)
    decisions = PB.build_decisions(sig, matrix)
    engine = Engine(signals=sig, matrix=matrix, decisions=decisions, headline=PB.headline(decisions),
                    product_data_is_demo=bool(provider.is_demo), provider=provider)
    with _lock:
        if len(_cache) > 16:
            _cache.clear()
        _cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, engine)
    for cb in list(_on_compute):
        cb(engine, s)
    return engine


def counts(engine: Engine) -> dict:
    return {
        "perlu_keputusan": sum(1 for d in engine.decisions if d["level"] == "perlu_keputusan"),
        "dipantau": sum(1 for d in engine.decisions if d["level"] == "pantau"),
        "normal": sum(1 for a in engine.signals.aspects if a["level"] == S.LEVEL_DEFAULT),
    }


def build_overview(engine: Engine, *, exposure_is_demo: bool, degraded_sources: list[str]) -> dict:
    sig = engine.signals
    return {
        "generated_at": dbm.to_iso(sig.now),
        "window_hours": S.WINDOW_HOURS,
        "composite": dict(sig.composite),
        "counts": counts(engine),
        "headline": engine.headline,
        "aspects": [dict(a) for a in sig.aspects],
        "provinces": [dict(p) for p in sig.provinces],
        "products": [dict(r) for r in engine.matrix],
        "decisions": [dict(d) for d in engine.decisions],
        "baseline_ready": sig.baseline_ready,
        "exposure_is_demo": bool(exposure_is_demo),
        "product_data_is_demo": engine.product_data_is_demo,
        "attributions": list(sig.attributions),
        "degraded_sources": list(degraded_sources),
        "levels": S.levels_legend(),
    }
