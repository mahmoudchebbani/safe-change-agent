# Safe Change Agent

An AI agent that helps engineers understand and safely change unfamiliar AWS serverless codebases. Capstone project for the [AI Engineering Buildcamp](https://maven.com/alexey-grigorev/from-rag-to-agents) (Cohort 4).

## The Problem

I work on a large serverless insurance system (Lambda, EventBridge, SQS, DynamoDB). Every spike in an unfamiliar part of it takes me 1–2 days, mostly spent rebuilding domain knowledge from old code, outdated Confluence/Miro docs and Slack threads. Changes to shared models (like a big DynamoDB policy object) break downstream Lambdas because nobody has a map of what reads or writes each field.

## What It Does

You give the agent a change request (for example *"add `claimChannel` to the ClaimAccepted event and propagate it to its consumers"*) and a target repo. The agent:

1. **Investigates** the code, infrastructure (CDK) and docs
2. Writes a **domain summary** with `file:line` citations and flags where the docs disagree with the code
3. Builds an **impact map**: every handler, library, event and queue that touches the change
4. Proposes a **plan** and waits for your approval

Next steps after the first version:

5. **Edits** the code in an isolated sandbox (git worktree, allow-listed commands only)
6. Runs **checks** (`tsc`, `cdk synth`, tests) and reviews its own diff
7. **Updates the docs** affected by the change
8. Returns a **report**: diff, impact map, checks run, risks and what it could not verify

The model provider is configurable: OpenAI or Amazon Bedrock.

## Target repos

The agent is built and evaluated on public AWS sample apps, cloned at pinned commits:

- **Main:** [serverless-eda-insurance-claims-processing](https://github.com/aws-samples/serverless-eda-insurance-claims-processing) — event-driven insurance claims (EventBridge, SQS, Step Functions, DynamoDB, API Gateway, Cognito, VPC, Bedrock, AgentCore Runtime, EventCatalog docs)
- **Stretch:** [generative-ai-use-cases](https://github.com/aws-samples/generative-ai-use-cases) — closed-network VPC and multiple AgentCore stacks

## Setup

1. Install uv if you don't have it yet: https://docs.astral.sh/uv/getting-started/installation/

2. Clone this repository (or download the zip and extract it).

3. Create a `.env` file from the template and add your API key:

       cp .env.example .env

4. Install dependencies:

       uv sync

5. Fetch the target repos (cloned into `targets/` at pinned commits):

       make targets

6. Start Jupyter:

       uv run jupyter notebook

Run the tests with `make test`.

## Notebooks

- `notebooks/01-setup.ipynb` - smoke test that confirms your environment works
- `notebooks/02-rag.ipynb` - a minimal RAG baseline you can adapt to your own data

## Project structure

```
src/safe_change_agent/   agent code (config, tools, agent, sandbox)
tests/                   unit and judge tests
eval/                    evaluation datasets and scripts
docs/                    project card and design notes
scripts/                 helper scripts (fetching target repos)
notebooks/               experiments
```

## Evaluation

See [eval/README.md](eval/README.md). Two hand-crafted datasets:

- **Understanding:** ~30 domain questions with expected answers and files
- **Changes:** ~20 hand-written change tasks + 5–10 real commits, each with the expected impacted files

## Status

Work in progress. See [docs/project-card.md](docs/project-card.md) for scope and plan.
