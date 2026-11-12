"""Run the agent on every scenario in batch and save the results.

uv run python eval/run_scenarios.py [scenarios.csv] [results.json]
uv run python eval/run_scenarios.py scenarios.csv results_remote.json --remote   # against the AgentCore deployment
"""
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from safe_change_agent.agent import create_agent  # noqa: E402
from safe_change_agent.config import get_model  # noqa: E402
from safe_change_agent.cost import cost_usd  # noqa: E402
from safe_change_agent.tools import create_codebase_tools  # noqa: E402

EVAL_DIR = Path(__file__).parent
CONCURRENCY = 5
RETRIES = 3


def collect_tool_calls(messages) -> list[dict]:
    calls = []
    for m in messages:
        for p in m.parts:
            if p.part_kind == "tool-call" and p.tool_name != "final_result":
                calls.append({"name": p.tool_name, "args": p.args_as_dict()})
    return calls


async def run_one(agent, model, scenario, semaphore):
    async with semaphore:
        start = time.time()
        for attempt in range(1, RETRIES + 1):
            try:
                result = await agent.run(scenario["question"])
                break
            except Exception as e:  # timeouts happen, retry then record the failure
                print(f"ERROR (attempt {attempt}) {scenario['question'][:60]}: {e}")
                if attempt == RETRIES:
                    return {**scenario, "output": None, "error": str(e)}

        usage = result.usage
        row = {
            **scenario,
            "output": result.output,
            "tool_calls": collect_tool_calls(result.new_messages()),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost": cost_usd(model, usage.input_tokens, usage.output_tokens),
            "execution_time": round(time.time() - start, 1),
        }
        print(f"{row['type']:16} {len(row['tool_calls']):3} tools ${row['cost']:.4f}  {row['question'][:60]}")
        return row


async def run_one_remote(scenario, semaphore):
    """Same row shape, but the deployed agent does the work (one AgentCore session per scenario)."""
    from safe_change_agent.remote import invoke_remote

    async with semaphore:
        start = time.time()
        for attempt in range(1, RETRIES + 1):
            try:
                r = await asyncio.to_thread(invoke_remote, scenario["question"])
                break
            except Exception as e:
                print(f"ERROR (attempt {attempt}) {scenario['question'][:60]}: {e}")
                if attempt == RETRIES:
                    return {**scenario, "output": None, "error": str(e)}
        if "error" in r:
            return {**scenario, "output": None, "error": r["error"]}
        row = {
            **scenario,
            "output": r["answer"],
            "tool_calls": r["tool_calls"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cost": r["cost_usd"],
            "execution_time": round(time.time() - start, 1),   # includes the AgentCore cold start
            "agent_time": r["execution_time"],
        }
        print(f"{row['type']:16} {len(row['tool_calls']):3} tools ${row['cost']:.4f}  {row['execution_time']:5}s  {row['question'][:60]}")
        return row


async def main(scenarios_file, results_file, remote=False):
    with open(scenarios_file) as f:
        scenarios = list(csv.DictReader(f))

    # rerunning keeps successful results and only runs new or failed scenarios
    done = {}
    if Path(results_file).exists():
        with open(results_file) as f:
            done = {r["question"]: r for r in json.load(f) if not r.get("error")}
    todo = [s for s in scenarios if s["question"] not in done]
    print(f"{len(done)} already done, running {len(todo)}")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    if remote:
        model = "remote"
        new = await asyncio.gather(*(run_one_remote(s, semaphore) for s in todo))
    else:
        model = get_model()
        agent = create_agent(create_codebase_tools(), model=model)
        new = await asyncio.gather(*(run_one(agent, model, s, semaphore) for s in todo))
    by_question = {**done, **{r["question"]: r for r in new}}
    results = [by_question[s["question"]] for s in scenarios]

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    total = sum(r.get("cost", 0) for r in results)
    errors = sum(1 for r in results if r.get("error"))
    print(f"\nSaved {len(results)} results to {results_file} ({errors} errors), model {model}, total ${total:.4f}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--remote"]
    scenarios_file = args[0] if len(args) > 0 else EVAL_DIR / "scenarios.csv"
    results_file = args[1] if len(args) > 1 else EVAL_DIR / "results.json"
    asyncio.run(main(scenarios_file, results_file, remote="--remote" in sys.argv))
