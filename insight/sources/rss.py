"""Feed RSS 2.0 / Atom generik.

- Feed dari INSIGHT_RSS_FEEDS (format: url, url|kategori, label=url, atau label=url|kategori; dipisah ';').
  Media komersial hanya aktif lewat env ini (bawaan kosong).
- Feed resmi bawaan yang memakai parser ini: KemkesRilisAdapter (RSS rilis berita Kemenkes).

Server HANYA mengambil URL feed dari konfigurasi/konstanta; URL item (link) hanya disimpan untuk ditampilkan dan
tidak pernah diambil oleh server. Feed dibaca bertahap (maks. MAX_FEED_ITEMS item pertama) supaya feed yang
sangat besar tidak perlu diunduh penuh. Parser RSS 2.0 diuji dengan contoh nyata (RSS berita WHO & Kemenkes).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from ..config import RssFeed, url_host
from ..models import RawItem
from .base import child_text, local, parse_date, parse_xml, stream_xml_entries

FEED_TIMEOUT_SECONDS = 20.0


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


def entry_to_raw(el: ET.Element, *, source: str, label: str, attribution: str,
                 default_category: str | None = None) -> RawItem | None:
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
        return None
    if not (title and link):
        return None
    return RawItem(source=source, source_label=label, attribution=attribution, title=title, url=link,
                   published_at=published, snippet=snippet, default_category=default_category)


def parse_feed(data: bytes, feed: RssFeed) -> list[RawItem]:
    root = parse_xml(data, f"RSS {feed.label}")
    attribution = f"Sumber: {feed.label}"
    items = (entry_to_raw(el, source=feed.key, label=feed.label, attribution=attribution,
                          default_category=feed.category) for el in root.iter())
    return [i for i in items if i is not None]


class RssAdapter:
    timeout_seconds = FEED_TIMEOUT_SECONDS + 5

    def __init__(self, feed: RssFeed):
        self.feed = feed
        self.name = feed.key
        self.label = feed.label
        self.attribution = f"Sumber: {feed.label}"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        entries = await stream_xml_entries(client, self.feed.url, label=f"RSS {self.feed.label}",
                                           allow_hosts=(url_host(self.feed.url),), timeout=FEED_TIMEOUT_SECONDS)
        items = (entry_to_raw(el, source=self.name, label=self.label, attribution=self.attribution,
                              default_category=self.feed.category) for el in entries)
        return [i for i in items if i is not None]


# ---------- Kemenkes: RSS rilis berita (diverifikasi 2026-11-03) ----------
# Ditemukan dari halaman resmi https://kemkes.go.id/id/rss/all. Respons nyata: RSS 2.0 (application/xml),
# ~33 MB berisi ~8.000 item terbaru-di-atas, waktu ke byte pertama ~18 detik → dibaca bertahap, maks. 40 item,
# dan dijalankan di latar belakang (slow=True) agar POST refresh tetap cepat.
KEMKES_RSS_URL = "https://kemkes.go.id/id/rss/article/rilis-berita"
KEMKES_MAX_ITEMS = 40
KEMKES_TIMEOUT_SECONDS = 45.0


class KemkesRilisAdapter:
    name = "kemkes_rilis"
    label = "Kemenkes Rilis Berita"
    attribution = "Sumber: Kementerian Kesehatan RI"
    slow = True
    timeout_seconds = KEMKES_TIMEOUT_SECONDS + 5

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        entries = await stream_xml_entries(client, KEMKES_RSS_URL, label="RSS Kemenkes",
                                           timeout=KEMKES_TIMEOUT_SECONDS, max_items=KEMKES_MAX_ITEMS)
        items = (entry_to_raw(el, source=self.name, label=self.label, attribution=self.attribution)
                 for el in entries)
        return [i for i in items if i is not None]
