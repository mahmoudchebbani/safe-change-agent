"""Ask the deployed agent a question.

    uv run python scripts/invoke_agentcore.py "Who listens for ClaimAccepted?"

Same as `safe-change-agent --remote "..."`; kept as a script for the deploy walkthrough.
"""
import json
import sys

from safe_change_agent.remote import invoke_remote

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What does this repo do?"
    result = invoke_remote(question)
    answer = result.pop("answer", None)
    print(json.dumps(result, indent=2))
    print("\n" + (answer or ""))
