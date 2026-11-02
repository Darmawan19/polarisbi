"""SQLite untuk Insight Hub (pola sama dengan polaris_auth.db).

File terpisah (default data/insight.db) supaya berita publik tidak tercampur dengan data akun
maupun DuckDB analitik. Semua waktu disimpan sebagai ISO 8601 UTC berakhiran Z.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS insight_items (
    id                TEXT PRIMARY KEY,
    source            TEXT NOT NULL,
    source_label      TEXT NOT NULL,
    attribution       TEXT NOT NULL,
    title             TEXT NOT NULL,
    snippet           TEXT NOT NULL DEFAULT '',
    url               TEXT NOT NULL,
    published_at      TEXT NOT NULL,
    fetched_at        TEXT NOT NULL,
    category          TEXT NOT NULL,
    province          TEXT,
    score             INTEGER NOT NULL,
    severity_verified INTEGER NOT NULL DEFAULT 0,
    dedupe_key        TEXT,
    meta_json         TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_insight_items_published ON insight_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_insight_items_score ON insight_items(score DESC);
CREATE INDEX IF NOT EXISTS idx_insight_items_category ON insight_items(category);
CREATE INDEX IF NOT EXISTS idx_insight_items_province ON insight_items(province);
CREATE INDEX IF NOT EXISTS idx_insight_items_dedupe ON insight_items(dedupe_key);

CREATE TABLE IF NOT EXISTS insight_source_status (
    source          TEXT PRIMARY KEY,
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_attempt_at TEXT,
    last_success_at TEXT,
    last_item_count INTEGER,
    last_error      TEXT
);

CREATE TABLE IF NOT EXISTS insight_cap_cache (
    guid       TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    ok         INTEGER NOT NULL,
    severity   TEXT,
    error      TEXT
);

CREATE TABLE IF NOT EXISTS insight_digests (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period            TEXT NOT NULL,
    bucket_key        TEXT NOT NULL,
    language          TEXT NOT NULL,
    period_start      TEXT NOT NULL,
    period_end        TEXT NOT NULL,
    generated_at      TEXT NOT NULL,
    generated_by      TEXT NOT NULL,
    status            TEXT NOT NULL,
    content_json      TEXT NOT NULL,
    impact_json       TEXT NOT NULL,
    item_ids_json     TEXT NOT NULL,
    attributions_json TEXT NOT NULL,
    exposure_is_demo  INTEGER NOT NULL,
    UNIQUE (period, bucket_key, language)
);
"""


def utcnow() -> datetime:
    """Dipisah supaya mudah dimanipulasi di tes."""
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    new_file = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    if new_file:
        try:
            os.chmod(path, 0o600)  # hanya pemilik; diabaikan di Windows
        except OSError:
            pass
    return conn


def init_schema(path: Path) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


@contextmanager
def session(path: Path):
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection):
    """Transaksi eksplisit (koneksi dalam mode autocommit)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
