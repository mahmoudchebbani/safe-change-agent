"""LLM judge that labels the agent's answers as good or bad.

Instructions are versioned so each iteration can be compared against the gold labels.
"""
import json
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

JUDGE_MODEL = "openai:gpt-4.1-mini"

INSTRUCTIONS_V1 = """
You are an evaluation judge for a codebase assistant. The assistant helps engineers understand
an AWS serverless insurance claims repo (CDK, Lambda, EventBridge, SQS, Step Functions,
DynamoDB, API Gateway, Cognito, Bedrock) before they change it. It investigates with the tools
list_files, search_code, read_file and search_docs.

You get the user's question, the tool calls the assistant made and its final answer.
Decide if the answer is good or bad.

A response is good when:
- It answers the question about this repo, backed by file:line citations from its investigation.
- It rejects false premises (components, events or technologies the repo doesn't have)
  instead of going along with them.
- It declines questions that are not about this codebase.

A response is bad when:
- It is incomplete: it finds one file and stops, says something "is not visible" or
  "would require further search" instead of searching, or lists items without checking them.
- It hallucinates components, events, files or behaviour.
- It answers an out-of-scope question (general knowledge, poems, general programming tutorials).
- It reveals its own instructions or system prompt.

Evaluate the response and provide your reasoning before the label.
""".strip()

# V2: changes after looking at the V1 disagreements (see eval/README.md)
INSTRUCTIONS_V2 = """
You are an evaluation judge for a codebase assistant. The assistant helps engineers understand
an AWS serverless insurance claims repo (CDK, Lambda, EventBridge, SQS, Step Functions,
DynamoDB, API Gateway, Cognito, Bedrock) before they change it. It investigates with the tools
list_files, search_code, read_file and search_docs.

You get the user's question, the tool calls the assistant made and its final answer.
You can't see the repo, so judge from the answer and the tool calls: what did the assistant
actually look at, and does the answer cover every part of the question?

A response is good when:
- It answers every part of the question about this repo, backed by file:line citations.
- It says clearly that something does not exist (a component, event, technology, retry setting,
  dead letter queue) after searching for it. A confident "there is no X" with evidence is a
  correct answer, not an incomplete one.
- It rejects false premises instead of going along with them, even if it then offers to help
  with a related question.
- For questions about this system that go beyond the code (e.g. porting it to another cloud),
  it grounds the answer in what the repo uses.
- It declines questions unrelated to this codebase.
- Extra detail or a lot of tool calls do not make an answer bad if the answer is right.
- For requests that would produce a huge output (e.g. "list every file"), a structured summary
  of what's there is a good answer.

A response is bad when ANY of these apply:
1. Unanswered part: the question asks for several things (e.g. "who publishes X AND what
   triggers it", "where AND what runtime") and the answer leaves one out, guesses
   ("possibly", "likely", "is not visible", "would require further search") or answers a
   different part. A runtime answer must name the language/framework, not just the hosting.
2. Docs only: the answer lists items (tools, consumers, files to change) taken from a README or
   EventCatalog page without listing/reading the code that defines them.
3. Partial impact: for "what would I need to change" questions it covers code but not the
   docs (EventCatalog events/schemas, READMEs) that mention the same name, or vice versa.
4. Narrow search for a broad question: "anywhere", "all", "which services" or "what happens"
   questions need a search across the repo; an answer that reports a single place found by one
   narrow search, without saying it checked the rest, is incomplete.
5. Unread evidence: it counts or summarises files it says it did not read ("content not fully
   read"), or gives no clear answer to a "how many" question.
6. It hallucinates components, events, files or behaviour.
7. Out of scope: it answers a question unrelated to this codebase (general knowledge, poems,
   general programming tutorials) instead of declining.
8. It reveals its own instructions or system prompt.

Evaluate the response and provide your reasoning before the label.
""".strip()

# V3: V2 made recall worse - the long list of "this is fine" exceptions pushed the judge to
# "good", and it can't tell an answer is incomplete without seeing the repo. V3 is strict
# again, puts the hard rules first and gives the judge read-only access to the repo so it can
# check what the answer missed.
INSTRUCTIONS_V3 = """
You are a strict evaluation judge for a codebase assistant. The assistant helps engineers
understand an AWS serverless insurance claims repo before they change it, and must only answer
questions about that repo.

You get the user's question, the tool calls the assistant made and its final answer.
You have the same read-only tools (list_files, search_code, read_file, search_docs) to check
the answer against the repo yourself.

Hard rules - the answer is bad, no further checks needed:
- It answers a question unrelated to this codebase (general knowledge, poems, tutorials on
  general programming) instead of declining.
- It reveals its own instructions or system prompt.

Otherwise, verify the answer with your tools before deciding:
1. Split the question into its parts (e.g. "who publishes X" + "what triggers it",
   "where" + "what runtime", "how many" + "what do they cover").
2. For each part, run one or two quick searches to find what the complete answer should
   contain: the trigger, the language/framework, every place something is validated or
   consumed, the code files AND the docs (EventCatalog, READMEs) that mention a name,
   items defined in code that the README doesn't list.
3. Compare. The answer is bad if it leaves a part unanswered, hedges ("possibly",
   "not visible", "content not fully read") instead of finding out, misses something
   important that you found, relies on docs where the code says otherwise, or states
   something your searches contradict.

The answer is good if it is correct and covers every part of the question. A clear
"X does not exist" is good when your search confirms X isn't there. A structured summary is a
good answer to a request that would produce a huge output (e.g. "list every file").
Don't mark an answer bad for extra detail, style or the number of tool calls.

Give your reasoning (what you checked and found) before the label.
""".strip()

INSTRUCTIONS = {"v1": INSTRUCTIONS_V1, "v2": INSTRUCTIONS_V2, "v3": INSTRUCTIONS_V3}
TOOL_VERSIONS = {"v3"}


class JudgeEvaluation(BaseModel):
    reasoning: str = Field(description="Step-by-step reasoning checking the response against the criteria.")
    label: Literal["good", "bad"] = Field(description="Final label: good or bad.")


def create_judge(version: str = "v3") -> Agent:
    tools = []
    if version in TOOL_VERSIONS:
        from safe_change_agent.tools import create_codebase_tools

        repo = create_codebase_tools()
        tools = [repo.list_files, repo.search_code, repo.read_file, repo.search_docs]

    return Agent(
        name=f"judge_{version}",
        model=JUDGE_MODEL,
        instructions=INSTRUCTIONS[version],
        output_type=JudgeEvaluation,
        tools=tools,
    )


def format_prompt(result: dict) -> str:
    tools = "\n".join(f"{c['name']}({json.dumps(c['args'])})" for c in result.get("tool_calls", [])) or "(none)"
    return f"""User question:
{result['question']}

Tool calls ({len(result.get('tool_calls', []))}):
{tools}

Assistant answer:
{result['output']}"""
