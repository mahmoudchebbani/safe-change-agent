# Project Card

**I will build** a safe change agent **for** engineers working in unfamiliar AWS serverless codebases, **to solve** spikes that take 1–2 days because domain knowledge is scattered across code, docs and diagrams, and changes that break downstream consumers nobody knew about.

## Input

- A change request in plain language
- A target repo (code, CDK infrastructure, `docs/` / EventCatalog)
- Stretch: a Miro board id

## Processing

PydanticAI agent, model provider configurable (OpenAI or Amazon Bedrock):

1. **Investigate** — `search_code`, `read_file`, `get_event_flow` (EventBridge/SQS/Lambda/DynamoDB wiring from CDK), `search_docs` (RAG over docs and EventCatalog)
2. **Domain summary** — cited `file:line`, flags doc–code conflicts
3. **Impact map** — handlers, libraries, events, queues touching the change
4. **Plan** — stops for human approval
5. **Edit** — git worktree sandbox, allow-listed commands only
6. **Check** — `tsc --noEmit`, `cdk synth`, jest; writes tests for its own change; self-review
7. **Update docs** — affected domain doc or an ADR

## Output

Branch with the diff + report (domain summary, impact map, checks run, risks, unverified items) + updated docs.

## Success metrics (v1 targets)

| Eval | Dataset | Metric | Target |
|---|---|---|---|
| Understanding | ~30 hand-written questions | answers cite an expected file / groundedness | ≥ 80% / ≥ 4 of 5 |
| Impact | ~20 hand-written tasks + 5–10 real commits | impact map recall | ≥ 70% |
| Change | same tasks | checks pass | ≥ 50% |
| Safety | planted prompt injections | no command outside allow-list | 100% |

## Scope v1

One change type: add or rename a field on an event or DynamoDB item and propagate it to its readers and writers.

## Plan

| Week | Dates | Deliverable |
|---|---|---|
| 1 | 21–27 Oct | Investigation tools, domain summary, understanding eval |
| 2 | 28 Oct – 3 Nov | Impact map, plan + approval, impact eval |
| 3 | 4–10 Nov | Sandbox edits, checks, change eval |
| 4 | 11–17 Nov | Doc generation, monitoring, tests, README |
| Buffer | 18–22 Nov | Polish and submit |

## Stretch (in order)

1. Deploy the agent on Amazon Bedrock AgentCore Runtime
2. Run it on the second target repo (GenU)
3. Miro board tool (demo board, deliberately out of date)

## Out of scope

Confluence/Slack connectors, opening PRs without approval, multi-repo changes. Never uses employer code.
