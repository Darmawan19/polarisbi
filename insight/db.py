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

-- Ronde 2: penanda "degraded" per sumber (tabel terpisah agar insight_source_status tidak berubah).
CREATE TABLE IF NOT EXISTS insight_source_health (
    source          TEXT PRIMARY KEY,
    degraded        INTEGER NOT NULL DEFAULT 0,
    degraded_reason TEXT,
    updated_at      TEXT NOT NULL
);

-- Ronde 2: jejak ringkasan otomatis (dasar batas panggilan LLM per hari).
CREATE TABLE IF NOT EXISTS insight_auto_digest_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    period      TEXT NOT NULL,
    bucket_key  TEXT NOT NULL,
    action      TEXT NOT NULL,
    llm_called  INTEGER NOT NULL DEFAULT 0,
    result      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insight_auto_digest_log_at ON insight_auto_digest_log(at);

-- Mesin keputusan: log keputusan (status hanya diubah manusia; upsert otomatis tidak menimpa status).
CREATE TABLE IF NOT EXISTS insight_decision (
    key           TEXT PRIMARY KEY,
    rule_id       TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    last_level    TEXT NOT NULL,
    last_title    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'baru',
    note          TEXT,
    updated_by    TEXT,
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_insight_decision_last_seen ON insight_decision(last_seen_at DESC);

-- Mesin keputusan: jejak perubahan status (append-only; dijaga trigger).
CREATE TABLE IF NOT EXISTS insight_decision_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL,
    dari_status TEXT,
    ke_status   TEXT NOT NULL,
    note        TEXT,
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insight_decision_event_key ON insight_decision_event(key, id);
CREATE TRIGGER IF NOT EXISTS trg_insight_decision_event_no_update BEFORE UPDATE ON insight_decision_event
BEGIN SELECT RAISE(ABORT, 'insight_decision_event bersifat append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_insight_decision_event_no_delete BEFORE DELETE ON insight_decision_event
BEGIN SELECT RAISE(ABORT, 'insight_decision_event bersifat append-only'); END;
"""

# Kolom tambahan pada tabel lama (ALTER TABLE ADD COLUMN, idempoten). Baris lama: NULL.
ADDED_COLUMNS = (
    ("insight_digests", "generated_trigger", "TEXT"),   # "auto" | "manual"; NULL = dibuat sebelum Ronde 2
)


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
        for table, column, decl in ADDED_COLUMNS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
                except sqlite3.OperationalError as e:   # proses lain menambahkannya bersamaan
                    if "duplicate column" not in str(e).lower():
                        raise
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
