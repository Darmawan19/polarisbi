"""Peringatan dini cuaca BMKG (nowcast). Format diverifikasi 2026-11-03.

RSS: https://www.bmkg.go.id/alerts/nowcast/id/rss.xml — item {title, link (URL file CAP), description,
guid, pubDate}. RSS TIDAK memuat tingkat keparahan; keparahan hanya ada di file CAP 1.2 per item
(<alert><info><severity>Moderate|Severe|Extreme</severity>).

Aturan pengambilan CAP:
- hanya untuk guid yang belum ada di insight_cap_cache, maksimal INSIGHT_CAP_MAX_PER_CYCLE per siklus;
- berurutan dengan jeda ~300 ms (batas BMKG 60 request/menit/IP);
- 429 atau error HTTP/timeout → berhenti untuk siklus ini (sisanya dicoba siklus berikutnya);
- kegagalan per guid (HTTP error selain 429, XML rusak, URL tidak sah) ikut di-cache agar tidak diulang;
- URL CAP TIDAK diambil mentah dari RSS: nama file divalidasi ketat lalu disusun ulang dari base URL tetap.
"""
from __future__ import annotations

import re

import httpx

from ..config import InsightSettings
from .. import db as dbm
from ..models import RawItem, SourceError
from ..provinces import detect_province
from .base import HttpStatusError, child_text, default_sleep, get_bytes, local, parse_date, parse_xml

RSS_URL = "https://www.bmkg.go.id/alerts/nowcast/id/rss.xml"
CAP_BASE = "https://www.bmkg.go.id/alerts/nowcast/id/"
_CAP_LINK_RE = re.compile(r"^https://www\.bmkg\.go\.id/alerts/nowcast/id/([A-Za-z0-9_-]{1,80}_alert\.xml)$")
CAP_DELAY_SECONDS = 0.3
_SEVERITIES = {"moderate": "Moderate", "severe": "Severe", "extreme": "Extreme", "minor": "Minor"}


def safe_cap_url(link: str | None) -> str | None:
    m = _CAP_LINK_RE.match((link or "").strip())
    return CAP_BASE + m.group(1) if m else None


def parse_rss(data: bytes) -> list[dict]:
    root = parse_xml(data, "RSS BMKG")
    out = []
    for it in root.iter():
        if local(it.tag) != "item":
            continue
        guid = child_text(it, "guid")
        link = child_text(it, "link")
        if not (guid or link):
            continue
        out.append({
            "guid": (guid or link)[:200], "link": link, "title": child_text(it, "title"),
            "description": child_text(it, "description"), "pubDate": child_text(it, "pubDate"),
        })
    return out


def parse_cap_severity(data: bytes) -> tuple[str | None, str | None]:
    """(severity, areaDesc) dari dokumen CAP."""
    root = parse_xml(data, "CAP BMKG")
    severity = area = None
    for el in root.iter():
        name = local(el.tag)
        if name == "severity" and severity is None:
            severity = _SEVERITIES.get((el.text or "").strip().lower())
        elif name == "areaDesc" and area is None:
            area = (el.text or "").strip() or None
    return severity, area


class BmkgWeatherAdapter:
    name = "bmkg_weather"
    label = "BMKG Peringatan Dini Cuaca"
    attribution = "Sumber: BMKG"

    def __init__(self, settings: InsightSettings, sleep=default_sleep):
        self.settings = settings
        self.sleep = sleep
        self.cap_requests = 0
        self.cap_stop_reason: str | None = None

    # ---- cache CAP ----
    def _load_cache(self, guids: list[str]) -> dict[str, dict]:
        if not guids:
            return {}
        with dbm.session(self.settings.db_path) as conn:
            q = ",".join("?" * len(guids))
            rows = conn.execute(f"SELECT * FROM insight_cap_cache WHERE guid IN ({q})", guids).fetchall()
        return {r["guid"]: dict(r) for r in rows}

    def _store(self, guid: str, ok: bool, severity: str | None, error: str | None) -> dict:
        row = {"guid": guid, "fetched_at": dbm.to_iso(dbm.utcnow()), "ok": 1 if ok else 0,
               "severity": severity, "error": (error or None) and error[:300]}
        with dbm.session(self.settings.db_path) as conn:
            conn.execute(
                "INSERT INTO insight_cap_cache(guid,fetched_at,ok,severity,error) VALUES (?,?,?,?,?)"
                " ON CONFLICT(guid) DO UPDATE SET fetched_at=excluded.fetched_at, ok=excluded.ok,"
                " severity=excluded.severity, error=excluded.error",
                (row["guid"], row["fetched_at"], row["ok"], row["severity"], row["error"]),
            )
        return row

    async def _fetch_caps(self, client: httpx.AsyncClient, entries: list[dict], cache: dict[str, dict]) -> None:
        pending = [e for e in entries if e["guid"] not in cache][: max(0, self.settings.cap_max_per_cycle)]
        for i, e in enumerate(pending):
            url = safe_cap_url(e["link"])
            if url is None:
                cache[e["guid"]] = self._store(e["guid"], False, None, "URL CAP tidak sah")
                continue
            if self.cap_requests:
                await self.sleep(CAP_DELAY_SECONDS)
            self.cap_requests += 1
            try:
                data = await get_bytes(client, url, label="CAP BMKG", max_bytes=1024 * 1024)
            except HttpStatusError as err:
                if err.status == 429:
                    self.cap_stop_reason = "429"
                else:
                    cache[e["guid"]] = self._store(e["guid"], False, None, str(err))
                    self.cap_stop_reason = f"http_{err.status}"
                break
            except SourceError as err:
                cache[e["guid"]] = self._store(e["guid"], False, None, str(err))
                self.cap_stop_reason = "error"
                break
            try:
                severity, area = parse_cap_severity(data)
            except SourceError as err:
                cache[e["guid"]] = self._store(e["guid"], False, None, str(err))
                continue
            row = self._store(e["guid"], severity is not None, severity,
                              None if severity else "severity tidak ada di CAP")
            row["area"] = area
            cache[e["guid"]] = row

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        data = await get_bytes(client, RSS_URL, label="RSS BMKG")
        entries = parse_rss(data)
        cache = self._load_cache([e["guid"] for e in entries])
        await self._fetch_caps(client, entries, cache)
        items: list[RawItem] = []
        for e in entries:
            c = cache.get(e["guid"])
            severity = c["severity"] if c and c["ok"] else None
            title = e["title"] or "Peringatan dini cuaca BMKG"
            province = detect_province(title) or (detect_province(c.get("area")) if c and c.get("area") else None)
            items.append(RawItem(
                source=self.name, source_label=self.label, attribution=self.attribution, title=title,
                url=e["link"], published_at=parse_date(e["pubDate"]), snippet=e["description"],
                category="bencana_alam", province=province, severity_verified=severity is not None,
                meta={"guid": e["guid"], "cap_severity": severity,
                      "cap_status": "ok" if severity else ("failed" if c else "pending")},
            ))
        return items
