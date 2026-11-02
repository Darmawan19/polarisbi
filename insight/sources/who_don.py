"""WHO Disease Outbreak News.

CATATAN: RSS DON lama (https://www.who.int/feeds/entity/csr/don/en/rss.xml) sudah 404 (dicek 2026-11-03),
begitu pula varian rss-feeds/disease-outbreak-news-english.xml. Sumber DON yang hidup adalah API OData
JSON resmi WHO: https://www.who.int/api/news/diseaseoutbreaknews (format diverifikasi 2026-11-03):
{"value": [{Id, Title, OverrideTitle, UseOverrideTitle ("True"/"False"), Summary (HTML), PublicationDate,
UrlName, DonId, ...}]}. Halaman item: https://www.who.int/emergencies/disease-outbreak-news/item/<UrlName>.
"""
from __future__ import annotations

import json
import re

import httpx

from ..models import RawItem, SourceError
from .base import get_bytes, parse_date

API_URL = "https://www.who.int/api/news/diseaseoutbreaknews"
API_PARAMS = {
    "$select": "Id,Title,OverrideTitle,UseOverrideTitle,Summary,PublicationDate,UrlName,DonId",
    "$orderby": "PublicationDate desc",
    "$top": "20",
}
ITEM_URL = "https://www.who.int/emergencies/disease-outbreak-news/item/"
_URLNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,200}$")


def parse_don(data: bytes) -> list[RawItem]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
        values = doc["value"]
        if not isinstance(values, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise SourceError("format JSON WHO DON tidak dikenali") from None
    items = []
    for v in values:
        if not isinstance(v, dict):
            continue
        use_override = str(v.get("UseOverrideTitle", "")).lower() == "true"
        title = (v.get("OverrideTitle") if use_override and v.get("OverrideTitle") else v.get("Title")) or ""
        url_name = str(v.get("UrlName") or "").strip()
        if not title or not _URLNAME_RE.match(url_name):
            continue
        items.append(RawItem(
            source=WhoDonAdapter.name, source_label=WhoDonAdapter.label, attribution=WhoDonAdapter.attribution,
            title=str(title), url=ITEM_URL + url_name, published_at=parse_date(v.get("PublicationDate")),
            snippet=str(v.get("Summary") or ""), category="kesehatan_wabah",
            meta={"don_id": str(v.get("DonId") or "")[:40]},
        ))
    return items


class WhoDonAdapter:
    name = "who_don"
    label = "WHO Disease Outbreak News"
    attribution = "Sumber: WHO"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        data = await get_bytes(client, API_URL, params=API_PARAMS, label="WHO DON")
        return parse_don(data)
