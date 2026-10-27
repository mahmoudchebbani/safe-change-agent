import logfire


def setup_monitoring() -> None:
    """Send PydanticAI traces (agent runs, LLM calls, tool calls) to Logfire.

    Uses LOGFIRE_TOKEN from the environment; without it, nothing is sent.

    Note: Logfire scrubs attributes whose names contain words like "session"
    (they look like secrets), so conversation ids and costs are logged as
    conversation_id / conversation_cost_usd.
    """
    logfire.configure(
        service_name="safe-change-agent",
        send_to_logfire="if-token-present",
        console=False,
    )
    logfire.instrument_pydantic_ai()
