"""USGS: feed gempa GeoJSON M4.5+ seminggu terakhir, disaring ke wilayah Indonesia.

Diverifikasi 2026-11-03: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson →
HTTP 200, application/json, FeatureCollection {metadata, features: [{id, properties: {mag, place, time (ms
epoch), url, title, tsunami (0/1), type, ...}, geometry: {coordinates: [lon, lat, kedalaman_km]}}]}.

Penyaringan: `place` memuat "Indonesia" atau nama laut di perairan Indonesia (USGS sering menulis "Banda Sea"
tanpa nama negara). Skor memakai aturan gempa yang sama dengan BMKG (magnitudo, kedalaman, tsunami).
Gempa yang sama bisa muncul dari BMKG dan USGS (id berbeda); keduanya disimpan dengan atribusi masing-masing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from ..models import RawItem, SourceError
from .base import get_bytes

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
TIMEOUT_SECONDS = 20.0
INDONESIA_PLACE_WORDS = ("indonesia", "banda sea", "molucca sea", "flores sea", "java sea", "savu sea",
                         "halmahera sea", "seram sea", "bali sea", "timor sea")


def _is_indonesia(place: str) -> bool:
    p = (place or "").lower()
    return any(w in p for w in INDONESIA_PLACE_WORDS)


def _num(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def parse_geojson(data: bytes) -> list[RawItem]:
    try:
        doc = json.loads(data.decode("utf-8-sig", errors="replace"))
    except ValueError:
        raise SourceError("respons USGS bukan JSON") from None
    feats = doc.get("features") if isinstance(doc, dict) else None
    if not isinstance(feats, list):
        raise SourceError("format GeoJSON USGS tidak dikenali")
    items: list[RawItem] = []
    for f in feats:
        if not isinstance(f, dict):
            continue
        p = f.get("properties") or {}
        if not isinstance(p, dict) or p.get("type", "earthquake") != "earthquake":
            continue
        place = str(p.get("place") or "")
        if not _is_indonesia(place) or not p.get("url") or not p.get("title"):
            continue
        coords = (f.get("geometry") or {}).get("coordinates") or []
        depth = _num(coords[2]) if len(coords) > 2 else None
        mag = _num(p.get("mag"))
        ms = _num(p.get("time"))
        published = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms is not None else None
        tsunami = bool(p.get("tsunami"))
        snippet = f"Magnitudo {mag} di {place}"
        if depth is not None:
            snippet += f", kedalaman {round(depth)} km"
        if tsunami:
            snippet += ". USGS menandai potensi tsunami."
        items.append(RawItem(
            source=UsgsQuakeAdapter.name, source_label=UsgsQuakeAdapter.label,
            attribution=UsgsQuakeAdapter.attribution, title=str(p["title"]), url=str(p["url"]),
            published_at=published, snippet=snippet, category="bencana_alam", severity_verified=True,
            meta={"magnitude": mag, "depth_km": depth, "tsunami": tsunami, "event_id": str(f.get("id") or "")[:40],
                  "lat": _num(coords[1]) if len(coords) > 1 else None, "lon": _num(coords[0]) if coords else None},
        ))
    return items


class UsgsQuakeAdapter:
    name = "usgs_quake"
    label = "USGS Earthquake Hazards"
    attribution = "Sumber: USGS"
    timeout_seconds = TIMEOUT_SECONDS + 5

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        return parse_geojson(await get_bytes(client, FEED_URL, label="USGS", timeout=TIMEOUT_SECONDS))
