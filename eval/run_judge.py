"""Run the judge on all results and measure alignment with the manual labels.

uv run python eval/run_judge.py v1
uv run python eval/run_judge.py v2
uv run python eval/run_judge.py v3   # judge with read-only repo tools
"""
import asyncio
import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from judge import create_judge, format_prompt  # noqa: E402

EVAL_DIR = Path(__file__).parent
CONCURRENCY = 5


async def judge_one(judge, result, semaphore):
    async with semaphore:
        for attempt in range(3):
            try:
                run = await judge.run(format_prompt(result))
                return {"label": run.output.label, "reasoning": run.output.reasoning,
                        "input_tokens": run.usage.input_tokens, "output_tokens": run.usage.output_tokens}
            except Exception as e:
                print(f"ERROR (attempt {attempt + 1}) {result['question'][:50]}: {e}")
        return {"label": "error", "reasoning": ""}


def alignment(rows):
    """'bad' is the positive class: we want the judge to catch failures."""
    tp = sum(r["label"] == "bad" and r["judge_label"] == "bad" for r in rows)
    fp = sum(r["label"] == "good" and r["judge_label"] == "bad" for r in rows)
    fn = sum(r["label"] == "bad" and r["judge_label"] == "good" for r in rows)
    tn = sum(r["label"] == "good" and r["judge_label"] == "good" for r in rows)
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": (tp + tn) / len(rows),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
    }


async def main(version):
    results = json.loads((EVAL_DIR / "results.json").read_text())
    with open(EVAL_DIR / "labels.csv") as f:
        labels = {row["question"]: row for row in csv.DictReader(f)}

    judge = create_judge(version)
    semaphore = asyncio.Semaphore(CONCURRENCY)
    labelled = [r for r in results if r["question"] in labels]
    verdicts = await asyncio.gather(*(judge_one(judge, r, semaphore) for r in labelled))

    rows = []
    for r, v in zip(labelled, verdicts):
        gold = labels[r["question"]]
        rows.append({
            "question": r["question"],
            "type": r["type"],
            "label": gold["label"],
            "failure_category": gold["failure_category"],
            "judge_label": v["label"],
            "judge_reasoning": v["reasoning"],
            "judge_input_tokens": v.get("input_tokens", 0),
            "judge_output_tokens": v.get("output_tokens", 0),
        })

    out_file = EVAL_DIR / f"judged_{version}.json"
    out_file.write_text(json.dumps(rows, indent=2))

    m = alignment(rows)
    print(f"\nJudge {version} on {len(rows)} labelled results -> {out_file.name}")
    print(f"TP {m['tp']}  FP {m['fp']}  FN {m['fn']}  TN {m['tn']}")
    from safe_change_agent.cost import cost_usd
    from judge import JUDGE_MODEL
    cost = sum(cost_usd(JUDGE_MODEL, r["judge_input_tokens"], r["judge_output_tokens"]) for r in rows)
    print(f"judge cost ${cost:.4f}")
    print(f"accuracy {m['accuracy']:.3f}  precision {m['precision']:.3f}  recall {m['recall']:.3f}")

    print("\nDisagreements:")
    for r in rows:
        if r["label"] != r["judge_label"]:
            print(f"\n- me: {r['label']} ({r['failure_category'] or '-'}), judge: {r['judge_label']}  [{r['type']}]")
            print(f"  Q: {r['question']}")
            print(f"  judge: {r['judge_reasoning'][:400]}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "v3"))
