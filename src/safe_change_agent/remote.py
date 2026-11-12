"""Call the agent deployed on Bedrock AgentCore Runtime.

The runtime ARN comes from .agentcore.json, written by scripts/deploy_agentcore.py.
"""
import json
import uuid
from pathlib import Path

import boto3

STATE_FILE = Path(__file__).resolve().parents[2] / ".agentcore.json"


def new_session_id() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:4]  # AgentCore wants >= 33 chars


def load_state() -> dict:
    if not STATE_FILE.exists():
        raise FileNotFoundError(f"{STATE_FILE} not found: deploy first with `make deploy`")
    return json.loads(STATE_FILE.read_text())


def invoke_remote(question: str, session_id: str | None = None) -> dict:
    """One question to the deployed agent; returns the entrypoint's response dict."""
    state = load_state()
    client = boto3.client("bedrock-agentcore", region_name=state["region"])
    response = client.invoke_agent_runtime(
        agentRuntimeArn=state["agentRuntimeArn"],
        runtimeSessionId=session_id or new_session_id(),
        contentType="application/json",
        accept="application/json",
        payload=json.dumps({"question": question}).encode(),
    )
    return json.loads(response["response"].read())
