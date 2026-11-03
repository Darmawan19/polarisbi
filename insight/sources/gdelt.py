"""GDELT DOC 2.0 API (https://api.gdeltproject.org/api/v2/doc/doc), mode=artlist, format=json.

STATUS VERIFIKASI (2026-11-03, diulang di Ronde 2): endpoint terjangkau, tetapi setiap query uji mengembalikan
`{}` (tanpa artikel) atau HTTP 429 dengan teks "Please limit requests to one every 5 seconds". Format daftar
artikel TIDAK bisa diverifikasi langsung; parser mengikuti dokumentasi resmi GDELT DOC 2.0:
{"articles": [{"url", "url_mobile", "title", "seendate": "YYYYMMDDTHHMMSSZ", "socialimage", "domain",
"language", "sourcecountry"}]}. `{}` diperlakukan sebagai nol artikel (bukan error).

Ronde 2:
- Maksimal 8 query per siklus, satu per aspek (lihat QUERIES), dikirim berurutan dengan jeda 5,5 detik.
- HTTP 429: tunggu BACKOFF_SECONDS lalu ulangi query itu sekali; bila masih 429, siklus berhenti dan sumber
  ditandai DEGRADED (degraded_reason), BUKAN error. Hasil parsial tetap dipakai.
- slow=True: pada POST refresh, GDELT dijalankan di latar belakang (lihat pipeline) agar respons < 60 detik.
"""
from __future__ import annotations

import json
import time

import httpx

from ..models import RawItem, SourceError
from .base import HttpStatusError, default_sleep, get_bytes, parse_date

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
# (aspek, query). Query ditentukan server (tidak pernah dari input pengguna). Maksimal MAX_QUERIES.
QUERIES: tuple[tuple[str, str], ...] = (
    ("bencana_alam", '(gempa OR banjir OR longsor OR erupsi OR tsunami OR "bencana alam") sourcecountry:indonesia'),
    ("kesehatan_wabah", '(wabah OR KLB OR pandemi OR "demam berdarah" OR outbreak) sourcecountry:indonesia'),
    ("ekonomi_makro", '(inflasi OR "suku bunga" OR "BI rate" OR rupiah OR "neraca perdagangan") '
                      'sourcecountry:indonesia'),
    ("pasar_keuangan", '(IHSG OR "bursa efek" OR obligasi OR "reksa dana" OR "trading halt") sourcecountry:indonesia'),
    ("regulasi", '(OJK OR POJK OR "Otoritas Jasa Keuangan") sourcecountry:indonesia'),
    ("industri_asuransi", '(asuransi OR "asuransi jiwa" OR reasuransi OR AAJI) sourcecountry:indonesia'),
    ("perbankan_bri", '("Bank Rakyat Indonesia" OR BBRI OR "BRI Life" OR "kredit usaha rakyat") '
                      'sourcecountry:indonesia'),
    ("perbankan_nasional", '(perbankan OR "kredit macet" OR "likuiditas bank" OR "suku bunga kredit") '
                           'sourcecountry:indonesia'),
)
MAX_QUERIES = 8
QUERY_SPACING_SECONDS = 5.5
BACKOFF_SECONDS = 15.0
TIME_BUDGET_SECONDS = 100.0
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_RECORDS = 25

assert len(QUERIES) <= MAX_QUERIES


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
    slow = True
    timeout_seconds = TIME_BUDGET_SECONDS + 2 * REQUEST_TIMEOUT_SECONDS

    def __init__(self, sleep=default_sleep, clock=time.monotonic):
        self.sleep = sleep
        self.clock = clock
        self.stop_reason: str | None = None
        self.degraded_reason: str | None = None

    async def _query(self, client: httpx.AsyncClient, q: str) -> list[RawItem]:
        params = {"query": q, "mode": "artlist", "format": "json", "maxrecords": str(MAX_RECORDS),
                  "timespan": "3d", "sort": "datedesc"}
        data = await get_bytes(client, API_URL, params=params, label="GDELT", timeout=REQUEST_TIMEOUT_SECONDS)
        return parse_artlist(data)

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        self.stop_reason = None
        self.degraded_reason = None
        start = self.clock()
        items: dict[str, RawItem] = {}
        ok_queries = 0
        last_error: str | None = None
        for i, (tag, q) in enumerate(QUERIES[:MAX_QUERIES]):
            if i:
                if self.clock() - start + QUERY_SPACING_SECONDS > TIME_BUDGET_SECONDS:
                    self.stop_reason = "time_budget"
                    break
                await self.sleep(QUERY_SPACING_SECONDS)
            parsed = None
            for attempt in (0, 1):
                try:
                    parsed = await self._query(client, q)
                    break
                except HttpStatusError as e:
                    last_error = str(e)
                    if e.status != 429:
                        break
                    if attempt == 0 and self.clock() - start + BACKOFF_SECONDS <= TIME_BUDGET_SECONDS:
                        await self.sleep(BACKOFF_SECONDS)     # backoff, lalu coba sekali lagi
                        continue
                    self.stop_reason = "429"
                    self.degraded_reason = ("GDELT membatasi laju (HTTP 429); siklus dihentikan setelah "
                                            f"{ok_queries} dari {len(QUERIES)} query")
                    break
                except SourceError as e:
                    last_error = str(e)
                    break
            if self.stop_reason == "429":
                break
            if parsed is None:
                continue
            ok_queries += 1
            for it in parsed:
                it.meta["query"] = tag
                items.setdefault(it.url, it)
        if ok_queries == 0 and last_error and self.degraded_reason is None:
            raise SourceError(last_error)
        return list(items.values())
