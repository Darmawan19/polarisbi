"""Shared read-only DuckDB executor. Returns (rows, columns)."""
import json
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv()

DUCKDB_PATH = os.getenv(
    "DUCKDB_PATH",
    str(Path(__file__).parent.parent / "polaris.duckdb"),
)


def execute_sql(sql: str) -> tuple[list[dict], list[str]]:
    """Execute SQL against DuckDB read-only. Returns (rows, columns). Max 100 rows."""
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        df = con.execute(sql).df()
        if len(df) > 100:
            df = df.head(100)
        rows = json.loads(df.to_json(orient="records", date_format="iso"))
        columns = list(df.columns)
        return rows, columns
    finally:
        con.close()
