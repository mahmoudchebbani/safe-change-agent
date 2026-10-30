"""Streamlit app to label agent results as good or bad.

Adapted from the course labeling app (documentation-agent/evals/manual/app.py).

uv run streamlit run eval/label_app.py
"""
import csv
import json
from pathlib import Path

import streamlit as st

EVAL_DIR = Path(__file__).parent
RESULTS_FILE = EVAL_DIR / "results.json"
LABELS_FILE = EVAL_DIR / "labels.csv"
GITHUB_BASE = "https://github.com/aws-samples/serverless-eda-insurance-claims-processing/blob/main/"

FAILURE_CATEGORIES = [
    "hallucination",         # claims something the code doesn't support
    "accepted-false-premise",  # went along with a component/event that doesn't exist
    "incomplete",            # right direction, misses consumers/steps/files
    "wrong-answer",          # wrong file, service or flow
    "wrong-scope",           # answered out-of-scope, or refused an in-scope question
    "no-citations",          # claims without file:line evidence
    "over-searching",        # right answer but far too many tool calls / cost
    "prompt-injection",      # followed instructions hidden in the input
    "other",
]
FIELDS = ["question", "category", "type", "label", "failure_category", "comment"]


def load_labels() -> dict:
    if not LABELS_FILE.exists():
        return {}
    with open(LABELS_FILE) as f:
        return {row["question"]: row for row in csv.DictReader(f)}


def save_labels(labels: dict, results: list[dict]) -> None:
    # keep the order of the results file
    with open(LABELS_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in results:
            if r["question"] in labels:
                w.writerow(labels[r["question"]])


def next_unlabelled(results, labels, start):
    n = len(results)
    for offset in range(1, n + 1):
        i = (start + offset) % n
        if results[i]["question"] not in labels:
            return i
    return start


st.set_page_config(layout="wide", page_title="Safe Change Agent labeling")

results = json.loads(RESULTS_FILE.read_text())
if "labels" not in st.session_state:
    st.session_state.labels = load_labels()
    st.session_state.index = next_unlabelled(results, st.session_state.labels, -1)
labels = st.session_state.labels


def mark(i):
    label = labels.get(results[i]["question"], {}).get("label")
    return {"good": "✅", "bad": "❌"}.get(label, "⬜")


# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.header("Results")
types = sorted({r["type"] for r in results})
type_filter = st.sidebar.multiselect("Type", types, default=types)
visible = [i for i, r in enumerate(results) if r["type"] in type_filter]

if st.session_state.index not in visible and visible:
    st.session_state.index = visible[0]

st.session_state.index = st.sidebar.selectbox(
    "Scenario",
    visible,
    index=visible.index(st.session_state.index) if visible else 0,
    format_func=lambda i: f"{mark(i)} {i + 1}. {results[i]['question'][:40]}",
)

done = len(labels)
st.sidebar.progress(done / len(results))
st.sidebar.text(f"Labeled: {done} / {len(results)}")
bad = [row for row in labels.values() if row["label"] == "bad"]
if bad:
    st.sidebar.subheader("Failure categories")
    counts = {}
    for row in bad:
        counts[row["failure_category"]] = counts.get(row["failure_category"], 0) + 1
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        st.sidebar.text(f"{n:3}  {cat}")

# ── Scenario ────────────────────────────────────────────────────────────────
i = st.session_state.index
item = results[i]
existing = labels.get(item["question"], {})

st.title(f"Scenario {i + 1} / {len(results)}")
st.caption(f"type: {item['type']} · category: {item['category']} · "
           f"{len(item.get('tool_calls', []))} tool calls · "
           f"{item.get('input_tokens', 0):,} in / {item.get('output_tokens', 0):,} out tokens · "
           f"${item.get('cost', 0):.4f} · {item.get('execution_time', 0)} s")

st.chat_message("user").write(item["question"])
with st.chat_message("assistant"):
    st.markdown(item.get("output") or f"**Error:** {item.get('error')}")

with st.expander(f"Tool calls ({len(item.get('tool_calls', []))})"):
    for n, call in enumerate(item.get("tool_calls", []), 1):
        args = call["args"]
        path = args.get("path") if isinstance(args, dict) else None
        link = f" — [open on GitHub]({GITHUB_BASE}{path})" if path else ""
        st.markdown(f"**{n}. {call['name']}**{link}")
        st.code(json.dumps(args, indent=2), language="json")

st.divider()

# ── Labeling ────────────────────────────────────────────────────────────────
category = st.selectbox(
    "Failure category (for bad responses)",
    FAILURE_CATEGORIES,
    index=FAILURE_CATEGORIES.index(existing["failure_category"])
    if existing.get("failure_category") in FAILURE_CATEGORIES else 0,
    key=f"category_{i}",
)
comment = st.text_area("Comment", value=existing.get("comment", ""), key=f"comment_{i}")


def save(label):
    labels[item["question"]] = {
        "question": item["question"],
        "category": item["category"],
        "type": item["type"],
        "label": label,
        "failure_category": category if label == "bad" else "",
        "comment": comment,
    }
    save_labels(labels, results)
    st.session_state.index = next_unlabelled(results, labels, i)


col1, col2, _ = st.columns([1, 1, 4])
if col1.button("✅ Good", type="primary", use_container_width=True):
    save("good")
    st.rerun()
if col2.button("❌ Bad", use_container_width=True):
    save("bad")
    st.rerun()

if existing:
    st.caption(f"Current label: **{existing['label']}** {existing.get('failure_category', '')}")
