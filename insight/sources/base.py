"""Protocol SourceAdapter + helper bersama (HTTP aman, parsing XML/tanggal)."""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable, Protocol, runtime_checkable

import httpx

from ..models import RawItem, SourceError

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
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


async def get_bytes(client: httpx.AsyncClient, url: str, *, params: dict | None = None,
                    label: str = "sumber", max_bytes: int = MAX_RESPONSE_BYTES) -> bytes:
    """GET dengan batas ukuran. URL HANYA berasal dari konstanta/konfigurasi server."""
    try:
        async with client.stream("GET", url, params=params) as resp:
            if resp.status_code != 200:
                raise HttpStatusError(resp.status_code, label)
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise SourceError(f"respons {label} terlalu besar")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.TimeoutException:
        raise SourceError(f"timeout saat menghubungi {label}") from None
    except httpx.HTTPError as e:
        raise SourceError(f"gagal menghubungi {label}: {type(e).__name__}") from None


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
