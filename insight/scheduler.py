"""Loop asyncio ringan untuk refresh sumber berkala (bawaan HIDUP: INSIGHT_SCHEDULER=on).

- Refresh pertama ±10 detik setelah startup (INSIGHT_SCHEDULER_STARTUP_DELAY), di latar belakang.
- Setelah itu tiap INSIGHT_REFRESH_MINUTES. Tidak pernah ada refresh ganda bersamaan: lock pipeline yang sama
  dengan POST refresh (AlreadyRunning → siklus dilewati); sumber lambat punya lock sendiri.
- Ringkasan otomatis berjalan lewat pemicu pasca-refresh (lihat auto_digest), bukan di scheduler.
"""
from __future__ import annotations

import asyncio
import logging

from . import pipeline
from .config import get_settings

log = logging.getLogger("insight")


class InsightScheduler:
    def __init__(self, interval_seconds: float | None = None, startup_delay: float | None = None):
        self.interval_seconds = interval_seconds
        self.startup_delay = startup_delay
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

    async def _wait(self, seconds: float) -> bool:
        """Tunggu; True bila diminta berhenti."""
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=max(0.0, seconds))
            return True
        except asyncio.TimeoutError:
            return False

    async def _loop(self) -> None:
        delay = self.startup_delay if self.startup_delay is not None else get_settings().scheduler_startup_delay
        if await self._wait(delay):
            return
        while not self._stop.is_set():
            try:
                await pipeline.refresh(defer_slow=True)
            except pipeline.AlreadyRunning:
                pass  # refresh manual sedang berjalan; lewati siklus ini
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("insight scheduler: refresh gagal (%s)", type(e).__name__)
            interval = self.interval_seconds or get_settings().refresh_minutes * 60
            if await self._wait(interval):
                return
