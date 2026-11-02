"""Adapter sumber data Insight Hub. Lihat base.SourceAdapter."""
from __future__ import annotations

from ..config import InsightSettings
from .base import SourceAdapter
from .bmkg_quake import BmkgQuakeAdapter
from .bmkg_weather import BmkgWeatherAdapter
from .gdelt import GdeltAdapter
from .rss import RssAdapter
from .who_don import WhoDonAdapter

BUILTIN = {
    "bmkg_quake": BmkgQuakeAdapter,
    "bmkg_weather": BmkgWeatherAdapter,
    "who_don": WhoDonAdapter,
    "gdelt": GdeltAdapter,
}

# Label & atribusi statis (dipakai /sources juga untuk sumber yang nonaktif).
BUILTIN_META = {key: (cls.label, cls.attribution) for key, cls in BUILTIN.items()}


def build_adapters(settings: InsightSettings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    for key in settings.sources:
        cls = BUILTIN[key]
        adapters.append(cls(settings) if key == "bmkg_weather" else cls())
    for feed in settings.rss_feeds:
        adapters.append(RssAdapter(feed))
    return adapters


__all__ = ["SourceAdapter", "build_adapters", "BUILTIN", "BUILTIN_META"]
