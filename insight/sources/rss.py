"""Feed RSS 2.0 / Atom generik dari INSIGHT_RSS_FEEDS (format label=url;label2=url2).

Server HANYA mengambil URL feed dari konfigurasi; URL item (link) hanya disimpan untuk ditampilkan dan
tidak pernah diambil oleh server. Parser RSS 2.0 diuji dengan contoh nyata (RSS berita WHO).
"""
from __future__ import annotations

import httpx

from ..config import RssFeed
from ..models import RawItem
from .base import child_text, get_bytes, local, parse_date, parse_xml


def _atom_link(entry) -> str:
    fallback = ""
    for c in entry:
        if local(c.tag) == "link":
            href = (c.get("href") or "").strip()
            rel = (c.get("rel") or "alternate").strip()
            if href and rel == "alternate":
                return href
            fallback = fallback or href
    return fallback


def parse_feed(data: bytes, feed: RssFeed) -> list[RawItem]:
    root = parse_xml(data, f"RSS {feed.label}")
    attribution = f"Sumber: {feed.label}"
    items: list[RawItem] = []
    for el in root.iter():
        name = local(el.tag)
        if name == "item":       # RSS 2.0
            title = child_text(el, "title")
            link = child_text(el, "link")
            if not link:
                guid = child_text(el, "guid")
                link = guid if guid.startswith(("http://", "https://")) else ""
            snippet = child_text(el, "description")
            published = parse_date(child_text(el, "pubDate") or child_text(el, "date"))
        elif name == "entry":    # Atom
            title = child_text(el, "title")
            link = _atom_link(el)
            snippet = child_text(el, "summary") or child_text(el, "content")
            published = parse_date(child_text(el, "published") or child_text(el, "updated"))
        else:
            continue
        if title and link:
            items.append(RawItem(source=feed.key, source_label=feed.label, attribution=attribution,
                                 title=title, url=link, published_at=published, snippet=snippet))
    return items


class RssAdapter:
    def __init__(self, feed: RssFeed):
        self.feed = feed
        self.name = feed.key
        self.label = feed.label
        self.attribution = f"Sumber: {feed.label}"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        data = await get_bytes(client, self.feed.url, label=f"RSS {self.feed.label}")
        return parse_feed(data, self.feed)
