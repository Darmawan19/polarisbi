"""Quick smoke-test for /api/ask/stream SSE endpoint."""

import json
import sys
import httpx

API_URL = "http://localhost:8000/api/ask/stream"
QUESTION = "total premi industri 2024 per kuartal"


def test_stream():
    print(f"Question: {QUESTION}\n{'=' * 60}")
    sql_received = False
    rows_received = False
    insight_tokens = []

    with httpx.stream(
        "POST",
        API_URL,
        json={"question": QUESTION, "language": "id"},
        timeout=60,
        headers={"Accept": "text/event-stream"},
    ) as response:
        if response.status_code != 200:
            print(f"ERROR: HTTP {response.status_code}")
            sys.exit(1)

        event_type = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                raw = line[5:].strip()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = raw

                if event_type == "status":
                    print(f"[status] {data}")
                elif event_type == "sql":
                    sql_received = True
                    print(f"\n[sql]\n{data.get('sql', '')}\n")
                    print(f"[interpretation] {data.get('interpretation', '')}\n")
                elif event_type == "rows":
                    rows_received = True
                    count = data.get("count", 0)
                    rows = data.get("rows", [])
                    print(f"[rows] {count} row(s) returned")
                    for r in rows[:5]:
                        print(f"  {r}")
                    print()
                elif event_type == "insight_token":
                    insight_tokens.append(data.get("token", ""))
                elif event_type == "error":
                    print(f"\n[ERROR] stage={data.get('stage')} message={data.get('message')}")
                    if "sql" in data:
                        print(f"  SQL: {data['sql']}")
                    sys.exit(1)
                elif event_type == "done":
                    break

    print("[insight]")
    print("".join(insight_tokens))
    print(f"\n{'=' * 60}")
    print(f"SQL received:   {'YES' if sql_received else 'NO'}")
    print(f"Rows received:  {'YES' if rows_received else 'NO'}")
    print(f"Insight tokens: {len(insight_tokens)}")
    print("--- DONE ---")


if __name__ == "__main__":
    test_stream()
