"""insight - Insight Hub: berita & data publik yang mempengaruhi bisnis asuransi jiwa di Indonesia.

Pemakaian di main.py (sesudah setup_auth(app)):

    from insight import setup_insight
    setup_insight(app)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import auto_digest
from . import db as dbm
from . import decisions
from . import overview
from . import pipeline
from .config import get_settings
from .router import router
from .scheduler import InsightScheduler


def setup_insight(app: FastAPI) -> None:
    """Buat tabel, daftarkan /api/insight/*, pasang pemicu auto-digest pasca-refresh, dan scheduler
    (bawaan hidup; matikan dengan INSIGHT_SCHEDULER=off).

    Pemicu auto-digest selalu terdaftar; saklarnya (INSIGHT_AUTO_DIGEST) dibaca saat pemicu berjalan.

    Scheduler dipasang dengan membungkus lifespan router yang sudah ada (kompatibel dengan FastAPI/Starlette
    terpasang, tanpa on_event yang sudah deprecated, dan tanpa mengganggu setup_auth).
    """
    dbm.init_schema(get_settings().db_path)
    app.include_router(router)
    pipeline.register_after_refresh(auto_digest.after_refresh)
    # mesin keputusan: simpan keputusan aktif setelah tiap refresh dan saat overview menghitung ulang
    pipeline.register_after_refresh(decisions.after_refresh)
    overview.on_compute(decisions.persist_engine)

    previous = app.router.lifespan_context
    scheduler = InsightScheduler()
    app.state.insight_scheduler = scheduler

    @asynccontextmanager
    async def lifespan(a):
        if get_settings().scheduler:
            scheduler.start()
        try:
            async with previous(a) as state:
                yield state
        finally:
            await scheduler.stop()

    app.router.lifespan_context = lifespan


__all__ = ["setup_insight"]
