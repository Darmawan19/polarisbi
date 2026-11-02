"""Pengaturan Insight Hub. Semua lewat environment variable (prefix INSIGHT_), semuanya opsional.

Dibaca ulang setiap dipanggil (sama seperti polaris_auth.config), jadi perubahan env saat tes
langsung berlaku.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

BUILTIN_SOURCES = ("bmkg_quake", "bmkg_weather", "who_don", "gdelt")
DEFAULT_SOURCES = "bmkg_quake,bmkg_weather,who_don,gdelt"
USER_AGENT = "PolarisBI-Insight/0.1"
MIN_REFRESH_MINUTES = 5


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.environ.get(name)
    try:
        val = int(raw) if raw not in (None, "") else default
    except ValueError:
        val = default
    if minimum is not None:
        val = max(minimum, val)
    return val


def _float(name: str, default: float, minimum: float | None = None) -> float:
    raw = os.environ.get(name)
    try:
        val = float(raw) if raw not in (None, "") else default
    except ValueError:
        val = default
    if minimum is not None:
        val = max(minimum, val)
    return val


def slugify(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    return s[:40] or "feed"


def is_http_url(url: str) -> bool:
    try:
        p = urlparse((url or "").strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


@dataclass(frozen=True)
class RssFeed:
    key: str      # "rss.<slug>"
    label: str
    url: str


def parse_rss_feeds(raw: str | None) -> tuple[RssFeed, ...]:
    """Format: label=url;label2=url2. Entri tidak valid (bukan http/https) diabaikan."""
    feeds: list[RssFeed] = []
    seen: set[str] = set()
    for part in (raw or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        label, url = part.split("=", 1)
        label, url = label.strip(), url.strip()
        if not label or not is_http_url(url):
            continue
        key = f"rss.{slugify(label)}"
        if key in seen:
            continue
        seen.add(key)
        feeds.append(RssFeed(key=key, label=label[:80], url=url))
    return tuple(feeds)


@dataclass(frozen=True)
class InsightSettings:
    db_path: Path
    sources: tuple[str, ...]          # sumber bawaan yang aktif
    rss_feeds: tuple[RssFeed, ...]    # aktif otomatis bila terisi
    http_timeout: float
    cap_max_per_cycle: int
    retention_days: int
    scheduler: bool
    refresh_minutes: int
    generate_cooldown_seconds: int
    exposure_provider: str

    @property
    def enabled_keys(self) -> tuple[str, ...]:
        return tuple(self.sources) + tuple(f.key for f in self.rss_feeds)


def get_settings() -> InsightSettings:
    default_db = Path(__file__).resolve().parent.parent / "data" / "insight.db"
    srcs = tuple(
        s.strip().lower()
        for s in os.environ.get("INSIGHT_SOURCES", DEFAULT_SOURCES).split(",")
        if s.strip().lower() in BUILTIN_SOURCES
    )
    return InsightSettings(
        db_path=Path(os.environ.get("INSIGHT_DB_PATH") or str(default_db)),
        sources=tuple(dict.fromkeys(srcs)),
        rss_feeds=parse_rss_feeds(os.environ.get("INSIGHT_RSS_FEEDS")),
        http_timeout=_float("INSIGHT_HTTP_TIMEOUT", 10.0, minimum=1.0),
        cap_max_per_cycle=_int("INSIGHT_CAP_MAX_PER_CYCLE", 20, minimum=0),
        retention_days=_int("INSIGHT_RETENTION_DAYS", 180, minimum=1),
        scheduler=_bool("INSIGHT_SCHEDULER", False),
        refresh_minutes=_int("INSIGHT_REFRESH_MINUTES", 30, minimum=MIN_REFRESH_MINUTES),
        generate_cooldown_seconds=_int("INSIGHT_GENERATE_COOLDOWN_SECONDS", 60, minimum=0),
        exposure_provider=(os.environ.get("INSIGHT_EXPOSURE_PROVIDER") or "demo").strip().lower(),
    )
