"""
reporting/assemble.py — Dynamic report assembly from AI-session findings.

Public API:
    assemble_report(findings, title="Insurance Data Briefing") -> dict
    assemble_deck(findings, title="Insurance Data Briefing") -> dict

findings: list of {"question": str, "sql": str | None}
assemble_report returns a report dict in the exact schema build_docx.build() expects.
assemble_deck returns a dict in the schema build_session.js expects.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

# ensure repo root is on path for llm / agent / database imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm import chat
from agent.sql_agent import generate_sql
from database.executor import execute_sql


# ─────────────────────────────────────────── SQL safety guard

_BANNED_KW = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|PRAGMA)\b",
    re.IGNORECASE,
)


def _is_safe(sql: str) -> tuple[bool, str]:
    """Return (True, '') or (False, reason). Rejects DML/DDL and multi-statement."""
    cleaned = re.sub(r"--[^\n]*", "", sql)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    stmts = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(stmts) > 1:
        return False, "multi-statement SQL rejected"
    m = _BANNED_KW.search(cleaned)
    if m:
        return False, f"forbidden keyword: {m.group(0)}"
    return True, ""


# ─────────────────────────────────────────── value formatting

def _fmt(col: str, val) -> str:
    """Format a raw DuckDB value for human-readable display."""
    if val is None:
        return ""
    col_up = col.upper()
    if isinstance(val, (int, float)):
        if any(k in col_up for k in ("IDR", "APE")):
            av = abs(val)
            if av >= 1e12:
                return f"Rp {val / 1e12:.2f}T"
            if av >= 1e9:
                return f"Rp {val / 1e9:.1f}B"
            if av >= 1e6:
                return f"Rp {val / 1e6:.1f}M"
        if "PCT" in col_up or "RASIO" in col_up:
            return f"{val:.1f}%"
        if "JUMLAH" in col_up or "POLIS" in col_up:
            return f"{int(val):,}"
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(int(val))
    return str(val)


def _rows_to_text(columns: list[str], rows: list[dict]) -> str:
    """Compact text table for LLM context (formatted values)."""
    header = " | ".join(columns)
    sep = "-" * min(len(header), 100)
    lines = [header, sep]
    for row in rows:
        lines.append(" | ".join(_fmt(c, row.get(c)) for c in columns))
    return "\n".join(lines)


# ─────────────────────────────────────────── exhibit heuristic (v1)

def _infer_exhibit(question: str, columns: list[str], rows: list[dict], idx: int) -> dict:
    """v1: PERIODE col + one measure column → trend; anything else → table."""
    if columns and columns[0].upper().startswith("PERIODE") and len(columns) == 2:
        return {
            "type": "trend",
            "caption": f"Exhibit {idx} — {question}",
            "labels": [str(r.get(columns[0], "")) for r in rows],
            "values": [_fmt(columns[1], r.get(columns[1])) for r in rows],
            "source": "DuckDB · OJK-schema",
        }
    return {
        "type": "table",
        "caption": f"Exhibit {idx} — {question}",
        "header": columns,
        "rows": [[_fmt(c, r.get(c)) for c in columns] for r in rows],
        "source": "DuckDB · OJK-schema (synthetic, 2024Q1–2024Q4)",
    }


# ─────────────────────────────────────────── deck exhibit builder

def _try_float(val) -> "float | None":
    """Parse a raw DuckDB value to float. Returns None if unparseable."""
    if isinstance(val, (int, float)):
        return float(val)
    if val is None:
        return None
    s = str(val).replace("Rp", "").replace("T", "").replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _infer_deck_exhibit(question: str, columns: list[str], rows: list[dict], idx: int) -> dict:
    """Build exhibit dict for the deck JSON schema.
    Time-series (PERIODE + one numeric measure) → chart; else → table.
    Falls back to table if any float parse fails.
    """
    caption = f"Exhibit {idx} — {question}"
    source = "DuckDB · OJK-schema (synthetic, 2024Q1–2024Q4)"

    is_time_series = len(columns) == 2 and columns[0].upper().startswith("PERIODE")
    if is_time_series:
        floats = [_try_float(r.get(columns[1])) for r in rows]
        if all(f is not None for f in floats):
            value_format = "#,##0.00" if any(abs(f) < 100 for f in floats) else "#,##0"
            return {
                "type": "chart",
                "caption": caption,
                "seriesName": columns[1],
                "labels": [str(r.get(columns[0], "")) for r in rows],
                "values": floats,
                "valueFormat": value_format,
                "source": source,
            }

    table_rows = [[_fmt(c, r.get(c)) for c in columns] for r in rows[:10]]
    highlight = None
    for ri, r in enumerate(rows[:10]):
        if "bri life" in str(r.get(columns[0], "")).lower():
            highlight = ri
            break
    ex: dict = {
        "type": "table",
        "caption": caption,
        "header": columns,
        "rows": table_rows,
        "source": source,
    }
    if highlight is not None:
        ex["highlightRow"] = highlight
    return ex


# ─────────────────────────────────────────── shared per-finding pipeline

def _run_pipeline(
    findings: list[dict],
) -> "list[tuple[str, list[str], list[dict], str, str, str]]":
    """Generate SQL → safety-check → execute → LLM insight for each finding.
    Returns list of (question, columns, rows, lead_in, analysis, sql).
    """
    processed = []
    for idx, f in enumerate(findings, start=1):
        question = f.get("question", "").strip()
        if not question:
            print(f"[assemble] Finding {idx}: empty question, skipping.")
            continue

        sql = f.get("sql") or None
        if not sql:
            try:
                sql, _ = generate_sql(question)
                print(f"[assemble] Finding {idx} SQL generated:\n{sql}")
            except Exception as exc:
                print(f"[assemble] Finding {idx}: SQL generation failed — {exc}")
                continue
        else:
            print(f"[assemble] Finding {idx} SQL (provided):\n{sql}")

        ok, reason = _is_safe(sql)
        if not ok:
            print(f"[assemble] Finding {idx} SKIPPED — {reason}")
            continue

        try:
            rows, columns = execute_sql(sql)
        except Exception as exc:
            print(f"[assemble] Finding {idx}: SQL execution failed — {exc}")
            continue

        print(f"[assemble] Finding {idx}: {len(rows)} rows, columns={columns}")
        if not rows:
            print(f"[assemble] Finding {idx}: no rows returned, skipping.")
            continue

        try:
            lead_in, analysis = _call_insight(question, columns, rows)
        except Exception as exc:
            lead_in, analysis = question, f"(LLM call failed: {exc})"

        processed.append((question, columns, rows, lead_in, analysis, sql))
    return processed


# ─────────────────────────────────────────── JSON helpers

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _parse_insight_json(raw: str, fallback_question: str) -> tuple[str, str]:
    text = _strip_fences(raw)
    try:
        d = json.loads(text)
        return d.get("lead_in", fallback_question), d.get("analysis", text)
    except json.JSONDecodeError:
        return fallback_question, text


def _parse_synthesis_json(raw: str) -> tuple[list[str], list[dict]]:
    text = _strip_fences(raw)
    try:
        d = json.loads(text)
        return d.get("exec_summary", []), d.get("recommendations", [])
    except json.JSONDecodeError:
        return [
            "This briefing was assembled from AI-session findings.",
            raw[:400],
        ], []


# ─────────────────────────────────────────── LLM calls

_INSIGHT_SYSTEM = (
    "You are a senior insurance analyst. "
    "Respond with ONLY a JSON object — no markdown fences, no prose outside the JSON.\n"
    'Schema: {"lead_in": "<one short bold sentence>", "analysis": "<2-4 sentences>"}\n'
    "STRICT RULES:\n"
    "- Use ONLY the numbers present in the table. Never invent figures.\n"
    "- If data is insufficient, say so plainly.\n"
    "- Return valid JSON. No ```json fences."
)

_SYNTHESIS_SYSTEM = (
    "You are a senior strategy consultant. "
    "Respond with ONLY a JSON object — no markdown fences, no prose outside the JSON.\n"
    "Schema:\n"
    '{"exec_summary": ["<para1>", "<para2>"],\n'
    ' "recommendations": [\n'
    '   {"title": "...", "body": "...", "owner": "...", "timeline": "...", "metric": "..."}\n'
    " ]}\n"
    "STRICT RULES:\n"
    "- exec_summary: exactly 2 paragraphs synthesising all findings.\n"
    "- recommendations: 2-3 items grounded in the findings.\n"
    "- Never invent numbers not present in the findings.\n"
    "- Return valid JSON. No ```json fences."
)


def _call_insight(question: str, columns: list[str], rows: list[dict]) -> tuple[str, str]:
    table_text = _rows_to_text(columns, rows[:25])
    user = (
        f"Question: {question}\n\n"
        f"Columns: {', '.join(columns)}\n\n"
        f"Data ({len(rows)} rows):\n{table_text}\n\n"
        "Return the JSON object."
    )
    raw = chat([{"role": "user", "content": user}], system=_INSIGHT_SYSTEM, max_tokens=500)
    return _parse_insight_json(raw, question)


def _call_synthesis(
    findings_data: list[tuple[str, str, str]], title: str
) -> tuple[list[str], list[dict]]:
    summary_input = "\n\n".join(
        f"Finding {i}: {q}\nLead-in: {li}\nAnalysis: {an}"
        for i, (q, li, an) in enumerate(findings_data, 1)
    )
    user = (
        f"Report title: {title}\n\n"
        f"Findings:\n{summary_input}\n\n"
        "Return the JSON object."
    )
    raw = chat([{"role": "user", "content": user}], system=_SYNTHESIS_SYSTEM, max_tokens=1000)
    return _parse_synthesis_json(raw)


# ─────────────────────────────────────────── main assembler

def assemble_report(
    findings: list[dict],
    title: str = "Insurance Data Briefing",
) -> dict:
    """
    findings: list of {"question": str, "sql": str | None}

    For each finding:
      1. Use provided SQL or generate it via generate_sql().
      2. Safety-check the SQL (single SELECT only).
      3. Execute against DuckDB (read-only, 100-row cap).
      4. Infer exhibit type (v1 heuristic).
      5. Call LLM for per-finding {lead_in, analysis}.

    Then call LLM once to synthesise exec_summary + recommendations.
    Returns the dict schema build_docx.build() expects.
    """
    today = date.today().strftime("%B %Y")
    processed = _run_pipeline(findings)

    # Synthesis (exec_summary + recommendations)
    findings_data = [(q, li, an) for q, _, _, li, an, _ in processed]
    if findings_data:
        try:
            exec_summary, recs = _call_synthesis(findings_data, title)
        except Exception as exc:
            exec_summary = [
                "This briefing was assembled from AI-session findings.",
                "See individual sections for detailed analysis.",
            ]
            recs = []
    else:
        exec_summary = [
            "No findings could be processed for this session.",
            "Please check the questions and try again.",
        ]
        recs = []

    # Build sections
    sections: list[dict] = []
    for i, (question, columns, rows, lead_in, analysis, _sql) in enumerate(processed, start=1):
        sections.append({
            "num": str(i),
            "title": question,
            "intro": "",
            "points": [(lead_in, analysis)],
            "exhibit": _infer_exhibit(question, columns, rows, i),
        })

    if recs:
        sections.append({
            "num": str(len(processed) + 1),
            "title": "What This Suggests",
            "intro": "Read together, the findings above point to a clear near-term agenda.",
            "recs": recs,
        })

    return {
        "meta": {
            "eyebrow": "PolarisBI · Generated from your AI session",
            "title": title,
            "subtitle": "Compiled from questions asked in the cockpit · live DuckDB data",
            "classification": "Generated report — PolarisBI Industry Intelligence",
            "author": "Lidharmawan Suryaatmadja",
            "date": today,
            "running_title": title,
            "footer": "Generated by PolarisBI · Industry Intelligence",
            "filename": "PolarisBI-Session-Report.docx",
        },
        "exec_summary": exec_summary,
        "sections": sections,
        "methodology": {
            "intro": (
                "Generated from the following Ask-AI questions, each translated to SQL "
                "and executed read-only against the PolarisBI DuckDB "
                "(OJK-schema, 2024Q1–2024Q4)."
            ),
            "sources": [f.get("question", "") for f in findings],
        },
    }


# ─────────────────────────────────────────── deck assembler

def assemble_deck(
    findings: list[dict],
    title: str = "Insurance Data Briefing",
) -> dict:
    """
    Assembles a deck JSON dict in the build_session.js schema from session findings.

    findings: list of {"question": str, "sql": str | None}
    Returns {"meta", "findings", "recommendations"}.
    """
    today = date.today().strftime("%B %Y")
    processed = _run_pipeline(findings)

    # Synthesis
    findings_data = [(q, li, an) for q, _, _, li, an, _ in processed]
    if findings_data:
        try:
            _exec_summary, recs = _call_synthesis(findings_data, title)
        except Exception as exc:
            print(f"[assemble_deck] synthesis failed — {exc}")
            recs = []
    else:
        recs = []

    # Build deck findings
    deck_findings = []
    for i, (question, columns, rows, lead_in, analysis, _sql) in enumerate(processed, start=1):
        takeaway = lead_in.strip().strip("*").strip()
        exhibit = _infer_deck_exhibit(question, columns, rows, i)
        deck_findings.append({
            "question": question,
            "takeaway": takeaway,
            "analysis": analysis,
            "exhibit": exhibit,
        })

    # Transform recs to deck schema {n, h, b, owner, timeline, metric}
    deck_recs = [
        {
            "n": str(i + 1),
            "h": r.get("title", ""),
            "b": r.get("body", ""),
            "owner": r.get("owner", ""),
            "timeline": r.get("timeline", ""),
            "metric": r.get("metric", ""),
        }
        for i, r in enumerate(recs)
    ]

    return {
        "meta": {
            "eyebrow": "Generated from your AI session",
            "title": title,
            "subtitle": "Compiled from questions asked in the cockpit · live DuckDB data",
            "author": "Lidharmawan Suryaatmadja",
            "date": today,
        },
        "findings": deck_findings,
        "recommendations": deck_recs,
    }
