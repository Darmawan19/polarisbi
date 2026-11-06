"""Model data Insight Hub: item mentah dari adapter, error API, dan skema respons (KONTRAK API)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel

PERIODS = ("daily", "weekly", "monthly")
CATEGORIES = ("bencana_alam", "kesehatan_wabah", "ekonomi_makro", "pasar_keuangan", "regulasi", "industri_asuransi",
              "perbankan_bri", "lainnya")
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
    default_category: str | None = None   # dipakai bila kata kunci tidak cocok kategori mana pun


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
    category: Optional[str] = None        # tambahan Ronde 2: kategori item pertama


class AspectSummary(BaseModel):
    category: str
    items: int
    max_score: int


class DigestContent(BaseModel):
    executive_summary: str
    key_events: list[KeyEvent]
    impact_note: str
    watchlist: list[str]
    aspects: Optional[list[AspectSummary]] = None   # tambahan Ronde 2: aspek yang terwakili di brief


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
    # tambahan Ronde 2: siapa yang memicu pembuatan brief ("auto" setelah refresh, "manual" lewat endpoint)
    generated_trigger: Optional[Literal["auto", "manual"]] = None


class GenerateRequest(BaseModel):
    # Divalidasi manual supaya error-nya berformat {code: invalid_period}.
    period: Optional[str] = None
    force: bool = False
    language: Optional[str] = "id"


class DecisionStatusRequest(BaseModel):
    # Divalidasi manual supaya error-nya berformat {code: invalid_status / invalid_note}.
    status: Optional[str] = None
    note: Optional[str] = None


class RefreshResult(BaseModel):
    source: str
    ok: bool
    new_items: int
    error: Optional[str]
    background: bool = False     # tambahan: sumber lambat yang dilanjutkan di latar belakang
    degraded: bool = False       # tambahan: sumber membatasi laju (mis. GDELT 429), bukan error


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
    degraded: bool = False                  # tambahan: siklus terakhir dibatasi laju oleh sumber
    degraded_reason: Optional[str] = None


class ExposureRow(BaseModel):
    province: str
    product: str
    active_policies: int


class ExposureResponse(BaseModel):
    is_demo: bool
    rows: list[ExposureRow]
