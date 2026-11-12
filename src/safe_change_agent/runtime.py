"""AgentCore Runtime entrypoint: wraps the agent in the HTTP contract AgentCore expects.

AgentCore calls POST /invocations with the JSON payload and GET /ping for health;
BedrockAgentCoreApp provides both. The container runs `python -m safe_change_agent.runtime`.

Payload:  {"question": "Who consumes ClaimAccepted?"}   ("prompt" is accepted as an alias)
Response: {"answer", "tool_calls", "input_tokens", "output_tokens", "cost_usd", "model", "execution_time"}
"""
import time

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from dotenv import load_dotenv

load_dotenv()

from safe_change_agent.agent import create_agent  # noqa: E402
from safe_change_agent.config import get_model  # noqa: E402
from safe_change_agent.cost import cost_usd  # noqa: E402
from safe_change_agent.monitoring import setup_monitoring  # noqa: E402
from safe_change_agent.tools import create_codebase_tools  # noqa: E402

setup_monitoring()

app = BedrockAgentCoreApp()

MODEL = get_model()
AGENT = create_agent(create_codebase_tools(), model=MODEL)


def tool_calls_of(messages) -> list[dict]:
    return [
        {"name": p.tool_name, "args": p.args_as_dict()}
        for m in messages
        for p in m.parts
        if p.part_kind == "tool-call" and p.tool_name != "final_result"
    ]


@app.entrypoint
async def invoke(payload: dict) -> dict:
    question = (payload.get("question") or payload.get("prompt") or "").strip()
    if not question:
        return {"error": "payload needs a 'question'"}

    start = time.time()
    result = await AGENT.run(question)
    usage = result.usage
    return {
        "answer": result.output,
        "tool_calls": tool_calls_of(result.new_messages()),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": round(cost_usd(MODEL, usage.input_tokens, usage.output_tokens), 5),
        "model": MODEL,
        "execution_time": round(time.time() - start, 1),
    }


if __name__ == "__main__":
    app.run()
