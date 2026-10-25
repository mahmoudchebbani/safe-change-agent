import os

from dotenv import load_dotenv

load_dotenv()


def get_model() -> str:
    """Return the PydanticAI model string for the configured provider."""
    provider = os.getenv("MODEL_PROVIDER", "openai")

    if provider == "openai":
        return "openai:" + os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if provider == "bedrock":
        return "bedrock:" + os.getenv(
            "BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

    raise ValueError(f"Unknown MODEL_PROVIDER: {provider}")
