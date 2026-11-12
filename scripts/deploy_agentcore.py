"""Deploy the agent container to Bedrock AgentCore Runtime.

    uv run python scripts/deploy_agentcore.py            # build, push, create/update, wait
    uv run python scripts/deploy_agentcore.py --no-build # reuse the last pushed image

Steps, each idempotent:
  1. ECR repository (created if missing)
  2. docker build (ARM64) + push, tagged with a timestamp and `latest`
  3. execution role: trust policy + the permissions from the AgentCore "runtime-permissions" doc,
     scoped to this account, region and agent name
  4. create-agent-runtime, or update-agent-runtime if it already exists; wait until READY
  5. write the runtime id/ARN to .agentcore.json (gitignored, read by the CLI's --remote)
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()
import os  # noqa: E402

REGION = os.getenv("AWS_REGION", "us-east-1")
AGENT_NAME = "safe_change_agent"                    # [a-zA-Z][a-zA-Z0-9_]{0,47}
ECR_REPO = "safe-change-agent"
ROLE_NAME = "safe-change-agent-agentcore-runtime"
ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / ".agentcore.json"

session = boto3.Session(region_name=REGION)
ACCOUNT = session.client("sts").get_caller_identity()["Account"]
ecr = session.client("ecr")
iam = session.client("iam")
control = session.client("bedrock-agentcore-control")


def sh(*args, input=None):
    print("$", " ".join(a if "password" not in a else "***" for a in args))
    subprocess.run(args, check=True, input=input, text=True)


def ensure_ecr_repo() -> str:
    try:
        repo = ecr.describe_repositories(repositoryNames=[ECR_REPO])["repositories"][0]
    except ClientError as e:
        if e.response["Error"]["Code"] != "RepositoryNotFoundException":
            raise
        repo = ecr.create_repository(
            repositoryName=ECR_REPO,
            imageScanningConfiguration={"scanOnPush": True},
            imageTagMutability="MUTABLE",
        )["repository"]
        print("created ECR repository", ECR_REPO)
    return repo["repositoryUri"]


def build_and_push(repo_uri: str) -> str:
    tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    image = f"{repo_uri}:{tag}"
    password = ecr.get_authorization_token()["authorizationData"][0]["authorizationToken"]
    import base64
    user, pwd = base64.b64decode(password).decode().split(":", 1)
    registry = repo_uri.split("/")[0]
    subprocess.run(["docker", "login", "--username", user, "--password-stdin", registry],
                   check=True, input=pwd, text=True)
    sh("docker", "build", "--platform", "linux/arm64", "-t", image, "-t", f"{repo_uri}:latest", str(ROOT))
    sh("docker", "push", image)
    sh("docker", "push", f"{repo_uri}:latest")
    return image


def ensure_role() -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AssumeRolePolicy",
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": ACCOUNT},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:*"},
            },
        }],
    }
    logs = f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group"
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Sid": "ECRImageAccess", "Effect": "Allow",
             "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
             "Resource": [f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{ECR_REPO}"]},
            {"Sid": "ECRTokenAccess", "Effect": "Allow", "Action": ["ecr:GetAuthorizationToken"], "Resource": "*"},
            {"Effect": "Allow", "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
             "Resource": [f"{logs}:/aws/bedrock-agentcore/runtimes/*"]},
            {"Effect": "Allow", "Action": ["logs:PutResourcePolicy"],
             "Resource": [f"{logs}:/aws/bedrock-agentcore/runtimes/{AGENT_NAME}-*"]},
            {"Effect": "Allow", "Action": ["logs:DescribeLogGroups"], "Resource": [f"{logs}:*"]},
            {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
             "Resource": [f"{logs}:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]},
            {"Effect": "Allow",
             "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"],
             "Resource": ["*"]},
            {"Effect": "Allow", "Action": "cloudwatch:PutMetricData", "Resource": "*",
             "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}},
            {"Sid": "GetAgentAccessToken", "Effect": "Allow",
             "Action": ["bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId"],
             "Resource": [f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:workload-identity-directory/default",
                          f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:workload-identity-directory/default/workload-identity/{AGENT_NAME}-*"]},
            {"Sid": "BedrockModelInvocation", "Effect": "Allow",
             "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
             "Resource": ["arn:aws:bedrock:*::foundation-model/*", f"arn:aws:bedrock:{REGION}:{ACCOUNT}:*"]},
        ],
    }
    try:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
        iam.update_assume_role_policy(RoleName=ROLE_NAME, PolicyDocument=json.dumps(trust))
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        role = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust),
                               Description="Execution role for the safe-change-agent AgentCore runtime")["Role"]
        print("created role", ROLE_NAME, "- waiting 10s for IAM to propagate")
        time.sleep(10)
    iam.put_role_policy(RoleName=ROLE_NAME, PolicyName="agentcore-runtime", PolicyDocument=json.dumps(policy))
    return role["Arn"]


def find_runtime() -> dict | None:
    for r in control.list_agent_runtimes(maxResults=100).get("agentRuntimes", []):
        if r["agentRuntimeName"] == AGENT_NAME:
            return r
    return None


def create_or_update_runtime(image: str, role_arn: str) -> dict:
    env = {"MODEL_PROVIDER": "bedrock", "BEDROCK_MODEL": os.getenv("BEDROCK_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")}
    if os.getenv("LOGFIRE_TOKEN"):
        env["LOGFIRE_TOKEN"] = os.environ["LOGFIRE_TOKEN"]   # traces from the cloud land in the same Logfire project
    common = {
        "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": image}},
        "roleArn": role_arn,
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "protocolConfiguration": {"serverProtocol": "HTTP"},
        "environmentVariables": env,
        "description": "Safe Change Agent: answers questions about an AWS serverless repo with citations",
    }
    existing = find_runtime()
    # AgentCore validates the role's ECR access at create/update time; a freshly attached
    # policy can take ~30s to propagate, so retry on that specific error
    for attempt in range(8):
        try:
            if existing:
                out = control.update_agent_runtime(agentRuntimeId=existing["agentRuntimeId"], **common)
                print("updated runtime", existing["agentRuntimeId"], "version", out.get("agentRuntimeVersion"))
            else:
                out = control.create_agent_runtime(agentRuntimeName=AGENT_NAME, **common)
                print("created runtime", out["agentRuntimeId"])
            return out
        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationException" and "ECR" in str(e) and attempt < 7:
                print(f"  role permissions not visible yet, retrying in 15s ({attempt + 1}/7)")
                time.sleep(15)
            else:
                raise


def wait_ready(runtime_id: str, timeout=600) -> dict:
    start = time.time()
    while True:
        rt = control.get_agent_runtime(agentRuntimeId=runtime_id)
        status = rt["status"]
        print(f"  status {status} ({int(time.time() - start)}s)")
        if status == "READY":
            return rt
        if status.endswith("FAILED") or status == "DELETING":
            raise SystemExit(f"runtime {status}: {rt.get('failureReason') or rt}")
        if time.time() - start > timeout:
            raise SystemExit("timed out waiting for READY")
        time.sleep(10)


def main():
    build = "--no-build" not in sys.argv
    repo_uri = ensure_ecr_repo()
    image = build_and_push(repo_uri) if build else f"{repo_uri}:latest"
    role_arn = ensure_role()
    out = create_or_update_runtime(image, role_arn)
    rt = wait_ready(out["agentRuntimeId"])
    state = {"agentRuntimeId": rt["agentRuntimeId"], "agentRuntimeArn": rt["agentRuntimeArn"],
             "version": rt.get("agentRuntimeVersion"), "image": image, "region": REGION,
             "deployed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    print("\nREADY:", rt["agentRuntimeArn"])
    print("state written to", STATE_FILE.name)


if __name__ == "__main__":
    main()
