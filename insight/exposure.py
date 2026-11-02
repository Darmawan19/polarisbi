"""Exposure BRI Life per provinsi & produk ("Dampak untuk BRI Life").

v1 hanya memakai DemoExposureProvider (data FIKTIF dari demo_exposure.csv). Titik penggantian ke data
warehouse: implementasikan ExposureProvider lalu daftarkan di PROVIDERS dan pilih lewat
INSIGHT_EXPOSURE_PROVIDER. Belum ada koneksi ke data apa pun.
"""
from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Protocol, runtime_checkable

from .config import InsightSettings, get_settings

log = logging.getLogger("insight")
DEMO_CSV = Path(__file__).resolve().parent / "demo_exposure.csv"


@runtime_checkable
class ExposureProvider(Protocol):
    is_demo: bool

    def get_exposure(self, provinces: Iterable[str] | None = None) -> list[dict]:
        """Baris {province, product, active_policies}. provinces=None → semua."""
        ...


@lru_cache(maxsize=4)
def _read_csv(path: str) -> tuple[tuple[str, str, int], ...]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append((r["province"].strip(), r["product"].strip(), int(r["active_policies"])))
    return tuple(rows)


class DemoExposureProvider:
    """Data fiktif deterministik. Semua respons yang memuatnya wajib exposure_is_demo=true."""
    is_demo = True

    def __init__(self, path: Path = DEMO_CSV):
        self.path = Path(path)

    def get_exposure(self, provinces: Iterable[str] | None = None) -> list[dict]:
        wanted = None if provinces is None else set(provinces)
        return [
            {"province": p, "product": prod, "active_policies": n}
            for p, prod, n in _read_csv(str(self.path))
            if wanted is None or p in wanted
        ]


PROVIDERS: dict[str, Callable[[InsightSettings], ExposureProvider]] = {
    "demo": lambda s: DemoExposureProvider(),
    # "warehouse": lambda s: WarehouseExposureProvider(...),  # nanti: agregat dari data warehouse
}


def get_provider(settings: InsightSettings | None = None) -> ExposureProvider:
    s = settings or get_settings()
    factory = PROVIDERS.get(s.exposure_provider)
    if factory is None:
        log.warning("INSIGHT_EXPOSURE_PROVIDER=%r tidak dikenal; memakai 'demo'.", s.exposure_provider)
        factory = PROVIDERS["demo"]
    return factory(s)
