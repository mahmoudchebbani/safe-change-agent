import sys
import uuid

import logfire
from dotenv import load_dotenv

load_dotenv()

from safe_change_agent.agent import create_agent  # noqa: E402
from safe_change_agent.config import get_model  # noqa: E402
from safe_change_agent.cost import CostAccumulator  # noqa: E402
from safe_change_agent.monitoring import setup_monitoring  # noqa: E402
from safe_change_agent.tools import create_codebase_tools  # noqa: E402


def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def run_session(first_question: str | None = None) -> CostAccumulator:
    """Interactive session: every question is one agent run, all grouped under one trace."""
    model = get_model()
    agent = create_agent(create_codebase_tools(), model=model)
    cost = CostAccumulator(model=model)
    session_id = uuid.uuid4().hex[:12]

    with logfire.span("cli conversation {conversation_id}", conversation_id=session_id, model=model) as span:
        message_history = []
        question = first_question or ask("Question (empty to stop): ")

        while question.strip():
            result = agent.run_sync(question, message_history=message_history)
            message_history = result.all_messages()
            cost.add(result.usage)

            logfire.info(
                "run finished",
                conversation_id=session_id,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                conversation_cost_usd=round(cost.total_cost, 6),
            )
            print(f"\n{result.output}\n")
            print(f"[run {cost.runs}: {result.usage.input_tokens} in / {result.usage.output_tokens} out tokens, "
                  f"session so far ${cost.total_cost:.4f}]\n")

            question = ask("Question (empty to stop): ")

        span.set_attribute("runs", cost.runs)
        span.set_attribute("input_tokens", cost.input_tokens)
        span.set_attribute("output_tokens", cost.output_tokens)
        span.set_attribute("cost_usd", round(cost.total_cost, 6))

    print(f"Session {session_id}: {cost.runs} runs, {cost.input_tokens} in / {cost.output_tokens} out tokens, "
          f"${cost.total_cost:.4f}")
    return cost


def run_remote_session(first_question: str | None = None) -> None:
    """Same loop, but every question goes to the agent deployed on AgentCore."""
    from safe_change_agent.remote import invoke_remote, new_session_id

    session_id = new_session_id()
    total_cost = 0.0
    question = first_question or ask("Question (empty to stop): ")
    while question.strip():
        result = invoke_remote(question, session_id)
        if "error" in result:
            print(f"\nerror: {result['error']}\n")
        else:
            total_cost += result.get("cost_usd", 0.0)
            print(f"\n{result['answer']}\n")
            print(f"[remote {result['model']}: {len(result['tool_calls'])} tool calls, "
                  f"{result['input_tokens']} in / {result['output_tokens']} out tokens, "
                  f"{result['execution_time']}s, session so far ${total_cost:.4f}]\n")
        question = ask("Question (empty to stop): ")


def main():
    args = sys.argv[1:]
    remote = "--remote" in args
    first = " ".join(a for a in args if a != "--remote") or None
    if remote:
        run_remote_session(first)
    else:
        setup_monitoring()
        run_session(first)


if __name__ == "__main__":
    main()
