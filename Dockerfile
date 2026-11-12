# AgentCore Runtime image: ARM64 only, serves POST /invocations and GET /ping on 8080.
# The pinned target repo is baked in so the agent has something to read.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1 \
    DOCKER_CONTAINER=1 \
    MODEL_PROVIDER=bedrock \
    BEDROCK_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0

# dependencies first so code changes don't reinstall them (no dev group, no `ui` extra: Streamlit is ~300 MB)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

# the repo the agent investigates (fetched with `make targets`, .git excluded via .dockerignore)
COPY targets/insurance-claims ./targets/insurance-claims

EXPOSE 8080
CMD ["uv", "run", "--no-sync", "python", "-m", "safe_change_agent.runtime"]
