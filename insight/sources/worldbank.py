"""World Bank Search API: berita/publikasi terkait Indonesia.

RSS berita World Bank tidak ditemukan (…/en/news/all?format=rss mengembalikan HTML, …/en/rss/news 404).
Yang diverifikasi 2026-11-03 adalah API JSON resmi (tanpa kunci):
https://search.worldbank.org/api/v2/news?format=json&rows=20&lang_exact=English&countcode=ID&fl=...
→ HTTP 200, application/json: {"rows", "os", "page", "total", "documents": {<id>: {id, url, title: {"cdata!"},
descr: {"cdata!"}, lnchdt (ISO 8601), displayconttype, count}, "facets": {...}}}, urut terbaru dulu.
Kategori bawaan ekonomi_makro (dipakai bila kata kunci tidak cocok kategori lain).
"""
from __future__ import annotations

import json

import httpx

from ..models import RawItem, SourceError
from .base import get_bytes, parse_date

API_URL = "https://search.worldbank.org/api/v2/news"
PARAMS = {"format": "json", "rows": "20", "lang_exact": "English", "countcode": "ID",
          "fl": "id,url,title,descr,lnchdt,displayconttype,count"}
TIMEOUT_SECONDS = 20.0


def _cdata(v) -> str:
    if isinstance(v, dict):
        v = v.get("cdata!", "")
    return str(v or "").strip()


def parse_news(data: bytes) -> list[RawItem]:
    try:
        doc = json.loads(data.decode("utf-8-sig", errors="replace"))
    except ValueError:
        raise SourceError("respons World Bank bukan JSON") from None
    docs = doc.get("documents") if isinstance(doc, dict) else None
    if not isinstance(docs, dict):
        raise SourceError("format JSON World Bank tidak dikenali")
    items: list[RawItem] = []
    for d in docs.values():
        if not isinstance(d, dict) or not d.get("url"):
            continue        # "facets" dan entri lain tanpa url
        title = _cdata(d.get("title"))
        if not title:
            continue
        url = str(d["url"]).strip()
        if url.startswith("http://www.worldbank.org/"):
            url = "https://" + url[len("http://"):]
        items.append(RawItem(
            source=WorldBankAdapter.name, source_label=WorldBankAdapter.label,
            attribution=WorldBankAdapter.attribution, title=title, url=url,
            published_at=parse_date(str(d.get("lnchdt") or "")), snippet=_cdata(d.get("descr")),
            default_category="ekonomi_makro",
            meta={"content_type": str(d.get("displayconttype") or "")[:60], "countries": str(d.get("count") or "")[:200]},
        ))
    return items


class WorldBankAdapter:
    name = "worldbank_id"
    label = "World Bank (Indonesia)"
    attribution = "Sumber: World Bank"
    timeout_seconds = TIMEOUT_SECONDS + 5

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        return parse_news(await get_bytes(client, API_URL, params=PARAMS, label="World Bank",
                                          timeout=TIMEOUT_SECONDS))
