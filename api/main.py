"""
PolarisBI FastAPI bridge.

Endpoints:
- GET  /api/health            → health check
- GET  /api/schema            → DuckDB schema description
- POST /api/ask/stream        → SSE streaming: question → SQL → rows → insight
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Optional

# Add parent directory to path so we can import Day 1 modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.sql_agent import generate_sql
from reporting import service as reporting_service
from database.setup import get_schema_description

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
# Resolve duckdb path relative to the repo root (parent of api/)
DUCKDB_PATH = os.getenv(
    "DUCKDB_PATH",
    str(Path(__file__).parent.parent / "polaris.duckdb"),
)

if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY missing in .env")

claude = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="PolarisBI API",
    description="AI Cockpit untuk IT Business Analyst Asuransi Indonesia",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://polarisbi-frontend.vercel.app",
        "https://polarisbi-frontend-darmawan19.vercel.app",
        "https://polarisbi-frontend-git-master-darmawan19.vercel.app",
    ],
    allow_origin_regex=r"https://polarisbi-frontend.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    language: str = "id"  # "id" or "en"


class FindingRequest(BaseModel):
    question: str
    sql: Optional[str] = None


class ReportRequest(BaseModel):
    title: Optional[str] = "Insurance Data Briefing"
    findings: Optional[list[FindingRequest]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def execute_sql(sql: str) -> list[dict]:
    """Execute SQL against DuckDB, return list of dicts. Max 100 rows."""
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        df = con.execute(sql).df()
        if len(df) > 100:
            df = df.head(100)
        return json.loads(df.to_json(orient="records", date_format="iso"))
    finally:
        con.close()


async def stream_insight(
    question: str, sql: str, rows: list[dict], language: str = "id"
) -> AsyncGenerator[str, None]:
    """Stream insurance insight from Claude based on query results."""
    lang_instruction = (
        "Tulis dalam Bahasa Indonesia formal yang ringkas (3-5 kalimat)."
        if language == "id"
        else "Write in concise formal English (3-5 sentences)."
    )

    system_prompt = f"""Anda adalah IT Business Data Analyst senior di industri asuransi Indonesia.

Tugas: berikan insight singkat dari hasil query SQL. {lang_instruction}

Format jawaban:
1. Headline angka kunci dengan satuan tepat (Rupiah dalam triliun/miliar, persen, dll)
2. Konteks domain: apa artinya untuk industri asuransi
3. Insight tambahan: trend, perbandingan, atau implikasi bisnis

JANGAN ulangi SQL atau tabel mentah — fokus interpretasi bisnis.
JANGAN pakai bullet list — pakai paragraf naratif.
JANGAN pakai markdown formatting (##, **, *, _) — tulis teks biasa saja."""

    user_message = f"""Pertanyaan user: {question}

SQL yang dijalankan:
```sql
{sql}
```

Hasil ({len(rows)} baris):
{json.dumps(rows[:20], indent=2, ensure_ascii=False)}

Berikan insight."""

    with claude.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "polarisbi-api",
        "model": CLAUDE_MODEL,
        "duckdb_path": DUCKDB_PATH,
        "duckdb_exists": Path(DUCKDB_PATH).exists(),
    }


@app.get("/api/schema")
async def schema():
    return {"schema": get_schema_description()}


@app.post("/api/ask/stream")
async def ask_stream(req: AskRequest):
    """Stream SSE: question → SQL → rows → insight tokens → done."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty")

    async def event_generator():
        try:
            # Step 1: generate SQL
            yield {
                "event": "status",
                "data": json.dumps(
                    {"stage": "generating_sql", "message": "Menerjemahkan ke SQL..."},
                    ensure_ascii=False,
                ),
            }

            try:
                sql, interpretation = generate_sql(req.question)
            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"stage": "sql_generation", "message": str(e)},
                        ensure_ascii=False,
                    ),
                }
                return

            yield {
                "event": "sql",
                "data": json.dumps(
                    {"sql": sql, "interpretation": interpretation},
                    ensure_ascii=False,
                ),
            }
            await asyncio.sleep(0.05)

            # Step 2: execute SQL
            yield {
                "event": "status",
                "data": json.dumps(
                    {"stage": "executing_sql", "message": "Menjalankan query di DuckDB..."},
                    ensure_ascii=False,
                ),
            }

            try:
                rows = execute_sql(sql)
            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"stage": "sql_execution", "message": str(e), "sql": sql},
                        ensure_ascii=False,
                    ),
                }
                return

            columns = list(rows[0].keys()) if rows else []
            yield {
                "event": "rows",
                "data": json.dumps(
                    {"rows": rows, "columns": columns, "count": len(rows)},
                    ensure_ascii=False,
                ),
            }
            await asyncio.sleep(0.05)

            # Step 3: stream insight
            yield {
                "event": "status",
                "data": json.dumps(
                    {"stage": "generating_insight", "message": "Menulis insight..."},
                    ensure_ascii=False,
                ),
            }

            async for token in stream_insight(req.question, sql, rows, req.language):
                yield {
                    "event": "insight_token",
                    "data": json.dumps({"token": token}, ensure_ascii=False),
                }

            # Step 4: done
            yield {
                "event": "done",
                "data": json.dumps({"status": "complete"}),
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"stage": "unexpected", "message": str(e)},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator())


# ── Report download ───────────────────────────────────────────────────────────

_MEDIA_TYPES = {
    "pdf":  "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@app.get("/api/report/options")
def report_options():
    return {"deck": ["pptx", "pdf"], "document": ["docx", "pdf"]}


@app.post("/api/report")
def generate_report(
    kind: str = "deck",
    fmt: str = "pptx",
    req: Optional[ReportRequest] = Body(default=None),
):
    # Session mode: findings present + document kind
    if req and req.findings and kind == "document":
        try:
            from reporting.assemble import assemble_report
            raw_findings = [{"question": f.question, "sql": f.sql} for f in req.findings]
            report = assemble_report(raw_findings, title=req.title or "Insurance Data Briefing")
            from reporting.document import build_docx
            docx_path = build_docx.build(report=report)
            if fmt == "pdf":
                from reporting import converters
                path = converters.to_pdf(docx_path)
            else:
                path = docx_path
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"dynamic report failed: {e}")
        media = _MEDIA_TYPES.get(fmt, "application/octet-stream")
        return FileResponse(str(path), media_type=media, filename=path.name)

    # Static mode (existing behaviour — deck or no-body document)
    try:
        path = reporting_service.generate_report(kind, fmt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"report generation failed: {e}")
    media = _MEDIA_TYPES.get(fmt, "application/octet-stream")
    return FileResponse(str(path), media_type=media, filename=path.name)


# ── Sparkline ─────────────────────────────────────────────────────────────────

@app.get("/api/sparkline/{kpi}")
async def sparkline(kpi: str):
    """Return sparkline data points (30 days or 4 quarters) untuk specified KPI.

    Supported KPIs:
    - premi_industri: total premi bruto industri per kuartal 2024
    - ape_brilife: APE BRI Life per kuartal 2024
    - rbc_brilife: RBC BRI Life per kuartal 2024
    - laba_brilife: laba bersih BRI Life per kuartal 2024
    - klaim_ratio: rasio klaim kesehatan industri per kuartal 2024
    - market_share_brilife: market share BRI Life per kuartal 2024
    """
    sparkline_queries = {
        "premi_industri": """
            SELECT PERIODE, ROUND(SUM(PREMI_BRUTO_IDR) / 1e12, 2) AS value
            FROM industry_aggregate
            WHERE PERIODE LIKE '2024%'
            GROUP BY PERIODE
            ORDER BY PERIODE ASC
        """,
        "ape_brilife": """
            SELECT PERIODE, ROUND(PREMI_BRUTO_IDR / 1e12, 2) AS value
            FROM industry_aggregate
            WHERE NAMA_PERUSAHAAN ILIKE '%BRI Life%' AND PERIODE LIKE '2024%'
            ORDER BY PERIODE ASC
        """,
        "rbc_brilife": """
            SELECT PERIODE, ROUND(RBC_PCT, 1) AS value
            FROM industry_aggregate
            WHERE NAMA_PERUSAHAAN ILIKE '%BRI Life%' AND PERIODE LIKE '2024%'
            ORDER BY PERIODE ASC
        """,
        "laba_brilife": """
            SELECT PERIODE, ROUND(PREMI_BRUTO_IDR / 1e9 * 0.07, 1) AS value
            FROM industry_aggregate
            WHERE NAMA_PERUSAHAAN ILIKE '%BRI Life%' AND PERIODE LIKE '2024%'
            ORDER BY PERIODE ASC
        """,
        "klaim_ratio": """
            SELECT PERIODE, ROUND(SUM(KLAIM_BRUTO_IDR) * 100.0 / SUM(PREMI_BRUTO_IDR), 1) AS value
            FROM industry_aggregate
            WHERE PERIODE LIKE '2024%'
            GROUP BY PERIODE
            ORDER BY PERIODE ASC
        """,
        "market_share_brilife": """
            WITH industry AS (
                SELECT PERIODE, SUM(PREMI_BRUTO_IDR) AS total
                FROM industry_aggregate
                WHERE PERIODE LIKE '2024%'
                GROUP BY PERIODE
            ),
            brilife AS (
                SELECT PERIODE, PREMI_BRUTO_IDR
                FROM industry_aggregate
                WHERE NAMA_PERUSAHAAN ILIKE '%BRI Life%' AND PERIODE LIKE '2024%'
            )
            SELECT b.PERIODE, ROUND(b.PREMI_BRUTO_IDR * 100.0 / i.total, 2) AS value
            FROM brilife b
            JOIN industry i ON b.PERIODE = i.PERIODE
            ORDER BY b.PERIODE ASC
        """,
    }

    if kpi not in sparkline_queries:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown KPI '{kpi}'. Available: {list(sparkline_queries.keys())}"
        )

    try:
        rows = execute_sql(sparkline_queries[kpi])
        return {
            "kpi": kpi,
            "points": [r["value"] for r in rows],
            "labels": [r["PERIODE"] for r in rows],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
