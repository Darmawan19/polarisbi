"""Pengaturan Insight Hub. Semua lewat environment variable (prefix INSIGHT_), semuanya opsional.

Dibaca ulang setiap dipanggil (sama seperti polaris_auth.config), jadi perubahan env saat tes
langsung berlaku.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger("insight")

BUILTIN_SOURCES = ("bmkg_quake", "bmkg_weather", "who_don", "gdelt", "usgs_quake", "kemkes_rilis", "worldbank_id")
DEFAULT_SOURCES = ",".join(BUILTIN_SOURCES)
USER_AGENT = "PolarisBI-Insight/0.1"
MIN_REFRESH_MINUTES = 5

# Kategori yang boleh dipakai sebagai kategori bawaan feed (url|kategori). Disalin dari models.CATEGORIES
# (tanpa "lainnya") supaya config tidak mengimpor models.
FEED_CATEGORIES = ("bencana_alam", "kesehatan_wabah", "ekonomi_makro", "pasar_keuangan", "regulasi",
                   "industri_asuransi", "perbankan_bri")

# ---------- SSRF: domain yang boleh diambil server ----------
# Host sumber bawaan (persis, tanpa wildcard subdomain). Host feed dari INSIGHT_RSS_FEEDS ditambahkan per
# adapter (dipercaya karena diatur operator), tetapi tetap tidak boleh IP literal/localhost/jaringan privat.
# Setiap hop redirect diperiksa ulang terhadap daftar yang sama.
BUILTIN_ALLOWED_HOSTS = (
    "data.bmkg.go.id", "www.bmkg.go.id",          # BMKG gempa & peringatan dini cuaca
    "www.who.int",                                # WHO Disease Outbreak News
    "api.gdeltproject.org",                       # GDELT DOC 2.0
    "earthquake.usgs.gov",                        # USGS GeoJSON
    "kemkes.go.id",                               # Kemenkes RSS rilis berita
    "search.worldbank.org",                       # World Bank Search API (berita)
)


def host_is_public_name(host: str | None) -> bool:
    """False untuk host kosong, localhost, atau IP literal (IP publik sekalipun: sumber harus ber-nama)."""
    h = (host or "").strip().lower().rstrip(".")
    if not h or h == "localhost" or h.endswith(".localhost") or h.endswith(".local") or h.endswith(".internal"):
        return False
    try:
        ipaddress.ip_address(h.strip("[]"))
        return False
    except ValueError:
        return True


def url_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


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
    category: str | None = None   # kategori bawaan (dipakai bila kata kunci tidak cocok kategori mana pun)


def _split_feed_entry(part: str) -> tuple[str, str, str | None] | None:
    """Satu entri → (label, url, kategori). Format: url | url|kategori | label=url | label=url|kategori."""
    if re.match(r"(?i)^https?://", part):
        label, rest = "", part
    elif "=" in part:
        label, rest = (x.strip() for x in part.split("=", 1))
        if not label:
            return None
    else:
        return None
    category = None
    if "|" in rest:
        rest, category = (x.strip() for x in rest.rsplit("|", 1))
        category = category.lower()
        if category not in FEED_CATEGORIES:
            log.warning("INSIGHT_RSS_FEEDS: kategori %r tidak dikenal; entri diabaikan.", category)
            return None
    if not is_http_url(rest) or not host_is_public_name(url_host(rest)):
        return None
    if not label:
        label = url_host(rest).removeprefix("www.")
    return label, rest, category


def parse_rss_feeds(raw: str | None) -> tuple[RssFeed, ...]:
    """Entri dipisah ';'. Tiap entri: url, url|kategori, label=url, atau label=url|kategori.

    Entri tidak valid (bukan http/https, host berupa IP/localhost, kategori tidak dikenal) diabaikan.
    Tanpa label, label = nama host tanpa "www.".
    """
    feeds: list[RssFeed] = []
    seen: set[str] = set()
    for part in (raw or "").split(";"):
        part = part.strip()
        if not part:
            continue
        parsed = _split_feed_entry(part)
        if parsed is None:
            continue
        label, url, category = parsed
        key = f"rss.{slugify(label)}"
        if key in seen:
            continue
        seen.add(key)
        feeds.append(RssFeed(key=key, label=label[:80], url=url, category=category))
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
    # --- Ronde 2: ringkasan otomatis setelah refresh ---
    auto_digest: bool = True
    auto_daily_min_minutes: int = 60
    auto_long_min_hours: int = 24
    auto_max_calls_per_day: int = 30
    scheduler_startup_delay: float = 10.0

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
        scheduler=_bool("INSIGHT_SCHEDULER", True),
        refresh_minutes=_int("INSIGHT_REFRESH_MINUTES", 30, minimum=MIN_REFRESH_MINUTES),
        generate_cooldown_seconds=_int("INSIGHT_GENERATE_COOLDOWN_SECONDS", 60, minimum=0),
        exposure_provider=(os.environ.get("INSIGHT_EXPOSURE_PROVIDER") or "demo").strip().lower(),
        auto_digest=_bool("INSIGHT_AUTO_DIGEST", True),
        auto_daily_min_minutes=_int("INSIGHT_AUTO_DAILY_MIN_MINUTES", 60, minimum=0),
        auto_long_min_hours=_int("INSIGHT_AUTO_LONG_MIN_HOURS", 24, minimum=0),
        auto_max_calls_per_day=_int("INSIGHT_AUTO_MAX_CALLS_PER_DAY", 30, minimum=0),
        scheduler_startup_delay=_float("INSIGHT_SCHEDULER_STARTUP_DELAY", 10.0, minimum=0.0),
    )
