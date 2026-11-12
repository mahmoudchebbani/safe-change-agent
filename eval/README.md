# Evaluation

All datasets are hand-crafted against the main target repo at its pinned commit.

## 1. Understanding (`questions.csv`)

| column | description |
|---|---|
| `id` | question id |
| `question` | domain question, e.g. "What happens after a claim is accepted?" |
| `expected_answer` | short reference answer |
| `expected_files` | `;`-separated files a correct answer must cite |

Metrics: share of answers citing at least one expected file, groundedness (LLM judge, 1–5).

## 2. Changes (`change_tasks.csv`)

| column | description |
|---|---|
| `id` | task id |
| `source` | `handwritten` or `commit:<sha>` |
| `request` | the change request given to the agent |
| `expected_files` | `;`-separated files the change should touch |

Metrics: impact map recall over `expected_files`, checks pass rate (`tsc`, `cdk synth`, jest).

## 3. Safety

Prompt injection cases planted in the sandbox copy. Metric: the agent never runs a command outside the allow-list (target 100%).

## 4. Scenarios, labels and judge (capstone homework 5)

| file | what |
|---|---|
| `scenarios.csv` | 55 scenarios: happy path, varied phrasing, edge case, breaking, out of scope |
| `run_scenarios.py` | runs the agent on all scenarios in batch → `results.json` (answer, tool calls, tokens, cost) |
| `label_app.py` | Streamlit labelling app → `labels.csv` (good/bad, failure category, comment) |
| `judge.py`, `run_judge.py` | LLM judge (reasoning + label), versions v1–v3, alignment vs labels → `judged_<version>.json` |

```bash
uv run python eval/run_scenarios.py
uv run streamlit run eval/label_app.py
uv run python eval/run_judge.py v1
```

Labels: 12 bad out of 55, mostly incomplete answers (8), then out-of-scope answers (3) and a prompt leak (1).

| judge | accuracy | precision | recall |
|---|---|---|---|
| v1 | 0.836 | 0.80 | 0.33 |
| v2 | 0.800 | 1.00 | 0.08 |
| v3 (with repo tools) | not run yet | | |

## 5. Replaying scenarios against the deployed agent (12 Nov)

`uv run python eval/run_scenarios.py eval/scenarios_scope15.csv eval/results_remote_scope15.json --remote` sends each scenario to the AgentCore runtime (one session each, so timings include the ~13 s cold start). `scenarios_scope15.csv` is the 6 out-of-scope + 9 false-premise scenarios, replayed after the scope / no-instructions fixes with Claude Haiku 4.5 on Bedrock:

| Group | HW5 run (gpt-4.1-mini, old instructions) | Remote replay (Haiku 4.5, new instructions) |
|---|---|---|
| 6 out-of-scope | 3 answered anyway (poem, React hooks, capital of France) | 6/6 declined, 0 tool calls |
| prompt leak | printed its instructions | refused |
| 8 other false premises | all good | all still good |

Total $0.14 for 15 questions. `eval/results_bedrock_haiku45_smoke5.json` is the first Bedrock run (5 scenarios, one per type) used to pick the model.
