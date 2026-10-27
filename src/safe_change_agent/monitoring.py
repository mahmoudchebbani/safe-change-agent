import logfire


def setup_monitoring() -> None:
    """Send PydanticAI traces (agent runs, LLM calls, tool calls) to Logfire.

    Uses LOGFIRE_TOKEN from the environment; without it, nothing is sent.
    """
    logfire.configure(
        service_name="safe-change-agent",
        send_to_logfire="if-token-present",
        console=False,
    )
    logfire.instrument_pydantic_ai()
