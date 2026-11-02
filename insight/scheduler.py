"""Loop asyncio ringan untuk refresh sumber berkala (default MATI: INSIGHT_SCHEDULER=off).

Scheduler HANYA me-refresh sumber; pembuatan brief tetap manual lewat endpoint (hemat biaya LLM).
"""
from __future__ import annotations

import asyncio
import logging

from . import pipeline
from .config import get_settings

log = logging.getLogger("insight")


class InsightScheduler:
    def __init__(self, interval_seconds: float | None = None):
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._stop: asyncio.Event | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._loop(), name="insight-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        if self._stop is not None:
            self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await pipeline.refresh()
            except pipeline.AlreadyRunning:
                pass  # refresh manual sedang berjalan; lewati siklus ini
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("insight scheduler: refresh gagal (%s)", type(e).__name__)
            interval = self.interval_seconds or get_settings().refresh_minutes * 60
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
