"""Protocol SourceAdapter + helper bersama (HTTP aman, parsing XML/tanggal)."""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable, Iterable, Protocol, runtime_checkable

import httpx

from ..models import RawItem, SourceError

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_FEED_ITEMS = 100
Sleep = Callable[[float], Awaitable[None]]


@runtime_checkable
class SourceAdapter(Protocol):
    name: str          # kunci sumber, mis. "bmkg_quake" atau "rss.antara"
    label: str         # nama untuk ditampilkan
    attribution: str   # wajib ikut tersimpan & tampil, mis. "Sumber: BMKG"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        """Ambil & parse item. Lempar SourceError bila sumber gagal total."""
        ...


class HttpStatusError(SourceError):
    def __init__(self, status: int, url_label: str):
        super().__init__(f"HTTP {status} dari {url_label}")
        self.status = status


def check_host_allowed(url: str, allow_hosts: Iterable[str] = (), label: str = "sumber") -> None:
    """SSRF: host harus ada di BUILTIN_ALLOWED_HOSTS atau allow_hosts (host feed dari env), harus nama
    (bukan IP literal/localhost), dan skema http/https."""
    from ..config import BUILTIN_ALLOWED_HOSTS, host_is_public_name, is_http_url, url_host

    host = url_host(url)
    allowed = set(BUILTIN_ALLOWED_HOSTS) | {h.lower() for h in allow_hosts}
    if not is_http_url(url) or not host_is_public_name(host) or host not in allowed:
        raise SourceError(f"host {host or '?'} tidak ada di daftar domain yang diizinkan ({label})")


@asynccontextmanager
async def open_stream(client: httpx.AsyncClient, url: str, *, params: dict | None = None, label: str = "sumber",
                      allow_hosts: Iterable[str] = (), timeout: float | None = None):
    """GET streaming dengan redirect manual: setiap hop diperiksa ulang terhadap daftar domain."""
    current, query = url, params
    extra = {"timeout": httpx.Timeout(timeout)} if timeout else {}
    try:
        for _hop in range(MAX_REDIRECTS + 1):
            check_host_allowed(current, allow_hosts, label)
            async with client.stream("GET", current, params=query, follow_redirects=False, **extra) as resp:
                if resp.status_code in REDIRECT_CODES and resp.headers.get("location"):
                    current, query = str(resp.url.join(resp.headers["location"])), None
                    continue
                if resp.status_code != 200:
                    raise HttpStatusError(resp.status_code, label)
                yield resp
                return
        raise SourceError(f"terlalu banyak redirect dari {label}")
    except httpx.TimeoutException:
        raise SourceError(f"timeout saat menghubungi {label}") from None
    except httpx.HTTPError as e:
        raise SourceError(f"gagal menghubungi {label}: {type(e).__name__}") from None


async def get_bytes(client: httpx.AsyncClient, url: str, *, params: dict | None = None,
                    label: str = "sumber", max_bytes: int = MAX_RESPONSE_BYTES,
                    allow_hosts: Iterable[str] = (), timeout: float | None = None) -> bytes:
    """GET dengan batas ukuran. URL HANYA berasal dari konstanta/konfigurasi server."""
    async with open_stream(client, url, params=params, label=label, allow_hosts=allow_hosts,
                           timeout=timeout) as resp:
        chunks, size = [], 0
        async for chunk in resp.aiter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise SourceError(f"respons {label} terlalu besar")
            chunks.append(chunk)
        return b"".join(chunks)


async def stream_xml_entries(client: httpx.AsyncClient, url: str, *, label: str = "sumber",
                             allow_hosts: Iterable[str] = (), timeout: float | None = None,
                             max_items: int = MAX_FEED_ITEMS, max_bytes: int = MAX_RESPONSE_BYTES) -> list[ET.Element]:
    """Baca feed RSS/Atom secara bertahap dan berhenti setelah max_items <item>/<entry> pertama.

    Untuk feed sangat besar (mis. RSS Kemenkes ~33 MB berisi ribuan item, terbaru di atas). Dokumen
    ber-ENTITY tetap ditolak; bila batas byte tercapai, item yang sudah lengkap tetap dipakai.
    """
    parser = ET.XMLPullParser(events=("end",))
    entries: list[ET.Element] = []
    tail, size = b"", 0
    async with open_stream(client, url, label=label, allow_hosts=allow_hosts, timeout=timeout) as resp:
        async for chunk in resp.aiter_bytes():
            window = (tail + chunk).upper()
            if b"<!ENTITY" in window:
                raise SourceError(f"XML {label} memuat ENTITY; ditolak")
            tail = chunk[-16:]
            size += len(chunk)
            try:
                parser.feed(chunk)
                for _ev, el in parser.read_events():
                    if local(el.tag) in ("item", "entry"):
                        entries.append(el)
            except ET.ParseError as e:
                if entries:
                    break
                raise SourceError(f"XML {label} tidak valid: {e}") from None
            if len(entries) >= max_items or size > max_bytes:
                break
    if not entries and size > max_bytes:
        raise SourceError(f"respons {label} terlalu besar")
    return entries[:max_items]


def parse_xml(data: bytes, label: str = "sumber") -> ET.Element:
    """Parse XML dari sumber luar. Dokumen ber-ENTITY ditolak (cegah entity expansion)."""
    if b"<!ENTITY" in data[:4096].upper() or b"<!ENTITY" in data.upper():
        raise SourceError(f"XML {label} memuat ENTITY; ditolak")
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise SourceError(f"XML {label} tidak valid: {e}") from None


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_text(el: ET.Element, name: str) -> str:
    for c in el:
        if local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def parse_date(raw: str | None) -> datetime | None:
    """RFC 822 (RSS), ISO 8601, atau format GDELT 20250101T120000Z → datetime UTC."""
    if not raw:
        return None
    s = raw.strip()
    dt: datetime | None = None
    if re.fullmatch(r"\d{8}T\d{6}Z", s):
        dt = datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if dt is None:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            dt = None
    if dt is None:
        try:
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError):
            dt = None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
