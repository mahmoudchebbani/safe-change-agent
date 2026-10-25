import re

import pytest

from tests.utils import collect_tools, run_agent_test


@pytest.mark.asyncio
async def test_agent_rejects_false_premise(agent):
    # Scenario 8: there is no payment service and no refund logic in the repo.
    # The agent must check and say so, not explain how refunds "probably" work.
    user_prompt = "How does the payment service refund the customer after a claim is rejected?"
    result = await run_agent_test(agent, user_prompt)

    tool_calls = collect_tools(result.new_messages())
    tool_names = [c.name for c in tool_calls]

    # it has to look before answering
    assert "list_files" in tool_names or "search_code" in tool_names

    answer = result.output.lower()

    # it has to say clearly that the payment service doesn't exist
    says_missing = re.search(
        r"(there is no|there's no|(does not|doesn't) (have|include|contain)( an?)?|no)\s+(\w+\s+)?[\"']?payment[\"']? service"
        r"|payment service[^.]{0,40}(does not|doesn't|did not|didn't) exist",
        answer,
    )
    assert says_missing, "agent didn't say the payment service doesn't exist"

    # and must not describe what the non-existent service does
    for invented in ["payment service handles", "payment service should", "lib/services/payment/app"]:
        assert invented not in answer, f"agent invented: {invented}"

    # and must not guess where refunds might live instead
    for guess in ["presumably", "likely", "probably", "can be inferred", "anticipated"]:
        assert guess not in answer, f"agent speculated: {guess}"
