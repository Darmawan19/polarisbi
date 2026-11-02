"""Model data Insight Hub: item mentah dari adapter, error API, dan skema respons (KONTRAK API)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel

PERIODS = ("daily", "weekly", "monthly")
CATEGORIES = ("bencana_alam", "kesehatan_wabah", "ekonomi_makro", "regulasi", "industri_asuransi", "lainnya")
SEVERITY_LABELS = ("rendah", "sedang", "tinggi", "sangat_tinggi")
LANGUAGES = ("id",)


class InsightError(HTTPException):
    """Format error sama dengan polaris_auth: {"detail": {"code", "message", ...}}."""

    def __init__(self, status_code: int, code: str, message: str = "", headers: dict | None = None, **extra):
        super().__init__(status_code=status_code, detail={"code": code, "message": message or code, **extra},
                         headers=headers)
        self.code = code


class SourceError(Exception):
    """Sumber gagal diambil/diparse. Pesannya aman untuk ditampilkan (tanpa secret)."""


@dataclass
class RawItem:
    """Item dari adapter sebelum dibersihkan, diklasifikasi, dan diberi skor."""
    source: str
    source_label: str
    attribution: str
    title: str
    url: str
    published_at: datetime | None
    snippet: str = ""
    category: str | None = None       # adapter boleh menetapkan (BMKG, WHO)
    province: str | None = None       # adapter boleh menetapkan (mis. dari kode wilayah BMKG)
    severity_verified: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


# ---------- skema respons (wajib identik dengan frontend) ----------

class FeedItem(BaseModel):
    id: str
    source: str
    source_label: str
    attribution: str
    title: str
    snippet: str
    url: str
    published_at: str
    fetched_at: str
    category: str
    province: Optional[str]
    score: int
    severity_label: str
    severity_verified: bool


class FeedResponse(BaseModel):
    items: list[FeedItem]
    total: int
    limit: int
    offset: int


class KeyEvent(BaseModel):
    text: str
    item_ids: list[str]


class DigestContent(BaseModel):
    executive_summary: str
    key_events: list[KeyEvent]
    impact_note: str
    watchlist: list[str]


class ExposureEntry(BaseModel):
    product: str
    active_policies: int


class ImpactRow(BaseModel):
    province: str
    events: int
    max_score: int
    total_active_policies: int
    exposure: list[ExposureEntry]


class DigestResponse(BaseModel):
    status: Literal["ready", "fallback", "not_generated"]
    period: str
    language: str
    bucket_key: Optional[str]
    period_start: Optional[str]
    period_end: Optional[str]
    generated_at: Optional[str]
    generated_by: Optional[Literal["llm", "template"]]
    is_stale: bool
    content: Optional[DigestContent]
    impact: list[ImpactRow]
    exposure_is_demo: bool
    items: list[FeedItem]
    attributions: list[str]


class GenerateRequest(BaseModel):
    # Divalidasi manual supaya error-nya berformat {code: invalid_period}.
    period: Optional[str] = None
    force: bool = False
    language: Optional[str] = "id"


class RefreshResult(BaseModel):
    source: str
    ok: bool
    new_items: int
    error: Optional[str]


class RefreshResponse(BaseModel):
    results: list[RefreshResult]
    finished_at: str


class SourceStatus(BaseModel):
    source: str
    label: str
    attribution: str
    enabled: bool
    status: Literal["ok", "stale", "error", "disabled"]
    last_attempt_at: Optional[str]
    last_success_at: Optional[str]
    last_item_count: Optional[int]
    last_error: Optional[str]


class ExposureRow(BaseModel):
    province: str
    product: str
    active_policies: int


class ExposureResponse(BaseModel):
    is_demo: bool
    rows: list[ExposureRow]
