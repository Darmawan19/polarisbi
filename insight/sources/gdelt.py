"""GDELT DOC 2.0 API (https://api.gdeltproject.org/api/v2/doc/doc), mode=artlist, format=json.

STATUS VERIFIKASI (2026-11-03): endpoint terjangkau, tetapi setiap query uji mengembalikan `{}` (tanpa
artikel) atau HTTP 429 dengan teks "Please limit requests to one every 5 seconds". Format daftar artikel
TIDAK bisa diverifikasi langsung; parser mengikuti dokumentasi resmi GDELT DOC 2.0:
{"articles": [{"url", "url_mobile", "title", "seendate": "YYYYMMDDTHHMMSSZ", "socialimage", "domain",
"language", "sourcecountry"}]}. `{}` diperlakukan sebagai nol artikel (bukan error).

Batas GDELT: 1 request per 5 detik → query dikirim berurutan dengan jeda 5,5 detik; berhenti saat 429
atau saat anggaran waktu internal habis (hasil parsial tetap dipakai).
"""
from __future__ import annotations

import json
import time

import httpx

from ..models import RawItem, SourceError
from .base import HttpStatusError, default_sleep, get_bytes, parse_date

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
# Query ditentukan server (tidak pernah dari input pengguna).
QUERIES: tuple[tuple[str, str], ...] = (
    ("bencana_alam", '("bencana alam" OR gempa OR longsor OR erupsi OR tsunami) sourcecountry:indonesia'),
    ("banjir", "banjir sourcecountry:indonesia"),
    ("wabah", '(wabah OR KLB OR pandemi OR "demam berdarah") sourcecountry:indonesia'),
    ("ekonomi", '(inflasi OR "suku bunga" OR "BI rate") sourcecountry:indonesia'),
    ("asuransi_ojk", "(asuransi OR OJK) sourcecountry:indonesia"),
)
QUERY_SPACING_SECONDS = 5.5
TIME_BUDGET_SECONDS = 40.0
MAX_RECORDS = 25


def parse_artlist(data: bytes) -> list[RawItem]:
    text = data.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return []
    try:
        doc = json.loads(text)
    except ValueError:
        raise SourceError("respons GDELT bukan JSON") from None
    if not isinstance(doc, dict):
        raise SourceError("format JSON GDELT tidak dikenali")
    arts = doc.get("articles") or []
    if not isinstance(arts, list):
        raise SourceError("format JSON GDELT tidak dikenali")
    items = []
    for a in arts:
        if not isinstance(a, dict) or not a.get("title") or not a.get("url"):
            continue
        domain = str(a.get("domain") or "").strip()
        items.append(RawItem(
            source=GdeltAdapter.name, source_label=GdeltAdapter.label, attribution=GdeltAdapter.attribution,
            title=str(a["title"]), url=str(a["url"]), published_at=parse_date(a.get("seendate")),
            snippet=f"Diberitakan oleh {domain}" if domain else "",
            meta={"domain": domain[:100], "language": str(a.get("language") or "")[:30]},
        ))
    return items


class GdeltAdapter:
    name = "gdelt"
    label = "GDELT Project"
    attribution = "Sumber: GDELT Project"

    def __init__(self, sleep=default_sleep, clock=time.monotonic):
        self.sleep = sleep
        self.clock = clock
        self.stop_reason: str | None = None

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        start = self.clock()
        items: dict[str, RawItem] = {}
        ok_queries = 0
        last_error: str | None = None
        for i, (tag, q) in enumerate(QUERIES):
            if i:
                if self.clock() - start + QUERY_SPACING_SECONDS > TIME_BUDGET_SECONDS:
                    self.stop_reason = "time_budget"
                    break
                await self.sleep(QUERY_SPACING_SECONDS)
            params = {"query": q, "mode": "artlist", "format": "json", "maxrecords": str(MAX_RECORDS),
                      "timespan": "3d", "sort": "datedesc"}
            try:
                data = await get_bytes(client, API_URL, params=params, label="GDELT")
                parsed = parse_artlist(data)
            except HttpStatusError as e:
                last_error = str(e)
                if e.status == 429:
                    self.stop_reason = "429"
                    break
                continue
            except SourceError as e:
                last_error = str(e)
                continue
            ok_queries += 1
            for it in parsed:
                it.meta["query"] = tag
                items.setdefault(it.url, it)
        if ok_queries == 0 and last_error:
            raise SourceError(last_error)
        return list(items.values())
