import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import chat
from database.setup import get_schema_description

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "sql_generator.md"


def _load_system_prompt() -> str:
    base_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    schema = get_schema_description()
    return f"{base_prompt}\n\n---\n\n## Skema Database Aktif\n\n{schema}"


def generate_sql(question: str) -> tuple[str, str]:
    system = _load_system_prompt()
    messages = [{"role": "user", "content": question}]
    raw = chat(messages, system=system, max_tokens=2000)

    # Extract ```sql ... ``` block
    match = re.search(r"```sql\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if not match:
        return raw.strip(), ""

    block = match.group(1).strip()
    lines = block.splitlines()

    interpretation = ""
    sql_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-- Interpretasi:"):
            interpretation = stripped[len("-- Interpretasi:"):].strip()
        else:
            sql_lines.append(line)

    sql = "\n".join(sql_lines).strip()
    return sql, interpretation
