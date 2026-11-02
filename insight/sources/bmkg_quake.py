"""Gempa terkini BMKG (Open Data BMKG, format diverifikasi 2026-11-03).

- gempaterkini.json   : 15 gempa M 5.0+ terakhir (punya field "Potensi" tsunami)
- gempadirasakan.json : 15 gempa dirasakan terakhir (punya field "Dirasakan", tanpa "Potensi")
Keduanya {"Infogempa": {"gempa": [ {Tanggal, Jam, DateTime, Coordinates, Magnitude, Kedalaman, Wilayah, ...} ]}}.
Kejadian yang sama di dua daftar digabung lewat kunci DateTime+Coordinates.
"""
from __future__ import annotations

import json
import re

import httpx

from ..models import RawItem, SourceError
from ..provinces import province_from_bmkg_region
from .base import get_bytes, parse_date

FEEDS = (
    ("https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json", "BMKG gempaterkini"),
    ("https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json", "BMKG gempadirasakan"),
)
# Halaman publik BMKG untuk ditampilkan (bukan untuk diambil server). Fragmen = id kejadian.
DISPLAY_URL = "https://www.bmkg.go.id/gempabumi/gempabumi-dirasakan"


def _num(raw: str | None) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", raw or "")
    return float(m.group(0).replace(",", ".")) if m else None


def _tsunami(potensi: str | None) -> bool:
    p = (potensi or "").lower()
    return "berpotensi tsunami" in p and "tidak berpotensi" not in p


def parse_quakes(data: bytes) -> list[dict]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
        gempa = doc["Infogempa"]["gempa"]
    except (ValueError, KeyError, TypeError):
        raise SourceError("format JSON gempa BMKG tidak dikenali") from None
    if isinstance(gempa, dict):  # autogempa.json berisi satu objek
        gempa = [gempa]
    return [g for g in gempa if isinstance(g, dict)]


def to_item(g: dict) -> tuple[str, RawItem] | None:
    published = parse_date(g.get("DateTime"))
    mag = _num(g.get("Magnitude"))
    if published is None or mag is None:
        return None
    depth = _num(g.get("Kedalaman"))
    wilayah = str(g.get("Wilayah") or "").strip()
    coords = str(g.get("Coordinates") or "").strip()
    event_key = published.strftime("%Y%m%dT%H%M%SZ") + (f"_{re.sub(r'[^0-9.,-]', '', coords)}" if coords else "")
    potensi = str(g.get("Potensi") or "").strip()
    tsunami = _tsunami(potensi)
    title = f"Gempa M{mag:.1f} - {wilayah}" if wilayah else f"Gempa M{mag:.1f}"
    parts = [f"Kedalaman {g.get('Kedalaman')}" if g.get("Kedalaman") else ""]
    if potensi:
        parts.append(potensi)
    if g.get("Dirasakan"):
        parts.append(f"Dirasakan (MMI): {g.get('Dirasakan')}")
    item = RawItem(
        source=BmkgQuakeAdapter.name, source_label=BmkgQuakeAdapter.label,
        attribution=BmkgQuakeAdapter.attribution, title=title, url=f"{DISPLAY_URL}#{event_key}",
        published_at=published, snippet=". ".join(p for p in parts if p),
        category="bencana_alam", province=province_from_bmkg_region(wilayah), severity_verified=True,
        meta={"magnitude": mag, "depth_km": depth, "tsunami": tsunami, "event_key": event_key,
              "coordinates": coords},
    )
    return event_key, item


class BmkgQuakeAdapter:
    name = "bmkg_quake"
    label = "BMKG Gempabumi"
    attribution = "Sumber: BMKG"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        merged: dict[str, RawItem] = {}
        errors: list[str] = []
        for url, label in FEEDS:
            try:
                data = await get_bytes(client, url, label=label)
                quakes = parse_quakes(data)
            except SourceError as e:
                errors.append(str(e))
                continue
            for g in quakes:
                res = to_item(g)
                if not res:
                    continue
                key, item = res
                if key in merged:
                    prev = merged[key]
                    # gabungkan info: Potensi tsunami dari gempaterkini, Dirasakan dari gempadirasakan
                    if item.snippet and item.snippet not in prev.snippet:
                        extra = [p for p in item.snippet.split(". ") if p not in prev.snippet]
                        prev.snippet = ". ".join([prev.snippet, *extra]).strip(". ")
                    prev.meta["tsunami"] = prev.meta["tsunami"] or item.meta["tsunami"]
                    prev.province = prev.province or item.province
                else:
                    merged[key] = item
        if errors and len(errors) == len(FEEDS):
            raise SourceError("; ".join(errors))
        return list(merged.values())
