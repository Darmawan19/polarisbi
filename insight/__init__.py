"""insight - Insight Hub: berita & data publik yang mempengaruhi bisnis asuransi jiwa di Indonesia.

Pemakaian di main.py (sesudah setup_auth(app)):

    from insight import setup_insight
    setup_insight(app)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db as dbm
from .config import get_settings
from .router import router
from .scheduler import InsightScheduler


def setup_insight(app: FastAPI) -> None:
    """Buat tabel, daftarkan /api/insight/*, dan pasang scheduler (bila INSIGHT_SCHEDULER=on).

    Scheduler dipasang dengan membungkus lifespan router yang sudah ada (kompatibel dengan FastAPI/Starlette
    terpasang, tanpa on_event yang sudah deprecated, dan tanpa mengganggu setup_auth).
    """
    dbm.init_schema(get_settings().db_path)
    app.include_router(router)

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
