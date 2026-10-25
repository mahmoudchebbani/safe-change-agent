import pytest

from tests.judge import assert_criteria
from tests.utils import run_agent_test


@pytest.mark.asyncio
async def test_event_consumer_ignores_metrics_widget(agent):
    # Scenario 9: Fraud.Detected is consumed only by the Notifications Service.
    # fraud-service.ts also mentions FRAUD_DETECTED, but in a CloudWatch metrics widget.
    user_prompt = "What consumes the Fraud.Detected event?"
    result = await run_agent_test(agent, user_prompt)

    await assert_criteria(result, [
        "the answer names the Notifications Service as the consumer of the Fraud.Detected event",
        "the answer does NOT present the CloudWatch metrics widget (createGraphWidget / createMetric in fraud-service.ts) as a consumer of the event",
        "the answer cites lib/claims-processing-stack.ts as the place where the Notifications Service subscribes to the event",
        "the agent called search_code with a pattern that matches how the code spells the event (FRAUD_DETECTED or Fraud.Detected), not only 'FraudDetected'",
    ])


@pytest.mark.asyncio
async def test_table_lookup_reads_cdk(agent):
    # Scenario 2: policies live in PolicyTable (customer-service.ts), keys PK / SK,
    # written by putPolicyRequests.js.
    user_prompt = "Which DynamoDB table stores customer policies, what are its keys, and which code writes to it?"
    result = await run_agent_test(agent, user_prompt)

    await assert_criteria(result, [
        "the answer names the table PolicyTable",
        "the answer says the keys are PK (partition key) and SK (sort key)",
        "the answer identifies putPolicyRequests.js as code that writes policies",
        "the agent called read_file on lib/services/customer/infra/customer-service.ts before answering",
    ])


@pytest.mark.xfail(reason="agent finds the Fargate app but doesn't trace API Gateway -> VPC Link -> ALB; needs the list_endpoints tool")
@pytest.mark.asyncio
async def test_settlement_endpoint_is_not_lambda(agent):
    # Scenario 10: POST /settlement goes through an HTTP API, a VPC Link and an ALB
    # to a Fargate service - there is no Lambda behind it.
    user_prompt = "What does the POST /settlement endpoint do and what runs behind it?"
    result = await run_agent_test(agent, user_prompt)

    await assert_criteria(result, [
        "the answer says the endpoint is an API Gateway HTTP API route integrated through a VPC Link with an Application Load Balancer",
        "the answer says the backend is a container service on ECS Fargate, and does NOT claim a Lambda function handles the request",
        "the answer cites lib/services/settlement/infra/settlement-service.ts",
    ])
