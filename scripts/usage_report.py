"""Summarise app/CLI conversations from Logfire: questions, tokens, tool calls and cost per conversation.

Usage: uv run python scripts/usage_report.py [days]
Needs LOGFIRE_READ_TOKEN in .env. One trace = one conversation.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from logfire.query_client import LogfireQueryClient

load_dotenv()


def main(days: int = 7):
    client = LogfireQueryClient(read_token=os.environ["LOGFIRE_READ_TOKEN"])
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = client.query_json_rows(sql="""
        SELECT trace_id,
               count(*) AS questions,
               sum((attributes->>'input_tokens')::bigint) AS input_tokens,
               sum((attributes->>'output_tokens')::bigint) AS output_tokens,
               sum((attributes->>'tool_calls')::bigint) AS tool_calls,
               sum((attributes->>'run_cost_usd')::double precision) AS cost
        FROM records
        WHERE span_name = 'run finished' AND attributes->>'question' IS NOT NULL
        GROUP BY trace_id
        ORDER BY min(start_timestamp)
    """, min_timestamp=since)["rows"]

    print(f"{'trace_id':34} {'q':>3} {'input':>9} {'output':>7} {'tools':>6} {'cost':>8}")
    for r in rows:
        print(f"{r['trace_id']:34} {r['questions']:>3} {r['input_tokens']:>9,} {r['output_tokens']:>7,} "
              f"{r['tool_calls']:>6} ${r['cost']:>7.4f}")

    n = len(rows)
    if n:
        q = sum(r["questions"] for r in rows)
        print(f"\n{n} conversations, {q} questions, "
              f"avg {sum(r['input_tokens'] for r in rows) / q:,.0f} input tokens/question, "
              f"total ${sum(r['cost'] for r in rows):.3f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
