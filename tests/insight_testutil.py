"""Helper bersama untuk tes Insight Hub (tanpa jaringan, DB sementara)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIX = ROOT / "tests" / "fixtures" / "insight"

ENV_KEYS = ("INSIGHT_SOURCES", "INSIGHT_RSS_FEEDS", "INSIGHT_HTTP_TIMEOUT", "INSIGHT_CAP_MAX_PER_CYCLE",
            "INSIGHT_RETENTION_DAYS", "INSIGHT_SCHEDULER", "INSIGHT_REFRESH_MINUTES",
            "INSIGHT_GENERATE_COOLDOWN_SECONDS", "INSIGHT_EXPOSURE_PROVIDER", "INSIGHT_AUTO_DIGEST",
            "INSIGHT_AUTO_DAILY_MIN_MINUTES", "INSIGHT_AUTO_LONG_MIN_HOURS", "INSIGHT_AUTO_MAX_CALLS_PER_DAY",
            "INSIGHT_SCHEDULER_STARTUP_DELAY")


def fixture_bytes(name: str) -> bytes:
    return (FIX / name).read_bytes()


class Clock:
    def __init__(self, dt: datetime):
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt

    def set(self, dt: datetime) -> None:
        self.dt = dt


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=timezone.utc)


async def no_sleep(_seconds: float) -> None:
    return None


@pytest.fixture
def insight_env(tmp_path, monkeypatch):
    """DB sementara, env bersih, LLM tidak pernah memanggil jaringan."""
    monkeypatch.setenv("INSIGHT_DB_PATH", str(tmp_path / "insight.db"))
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    # Tes TIDAK PERNAH menjalankan scheduler (bawaan produksi = on) dan auto-digest hanya dinyalakan eksplisit.
    monkeypatch.setenv("INSIGHT_SCHEDULER", "off")
    monkeypatch.setenv("INSIGHT_AUTO_DIGEST", "off")
    from insight import db as dbm
    from insight import llm as insight_llm

    async def _no_llm(*a, **k):
        raise insight_llm.LLMUnavailable("tes: LLM dimatikan")

    monkeypatch.setattr(insight_llm, "complete", _no_llm)
    dbm.init_schema(tmp_path / "insight.db")
    return tmp_path


def mock_client_factory(handler):
    def factory(_settings):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return factory


def insert_item(conn, *, id, title="Judul", source="gdelt", score=50, published_at="2026-11-03T00:00:00Z",
                fetched_at=None, province=None, category="bencana_alam", snippet="", dedupe_key=None,
                meta_json="{}", attribution="Sumber: GDELT Project", source_label="GDELT Project"):
    conn.execute(
        "INSERT INTO insight_items(id,source,source_label,attribution,title,snippet,url,published_at,fetched_at,"
        "category,province,score,severity_verified,dedupe_key,meta_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (id, source, source_label, attribution, title, snippet, f"https://example.org/{id}", published_at,
         fetched_at or published_at, category, province, score, 0, dedupe_key, meta_json),
    )
