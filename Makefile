.PHONY: setup targets test docker-build docker-run invoke-local

IMAGE ?= safe-change-agent:local

setup:
	uv sync --all-extras

targets:
	./scripts/fetch_targets.sh

test:
	uv run pytest

# --- AgentCore container (ARM64) ---

docker-build:
	docker build --platform linux/arm64 -t $(IMAGE) .

# runs the container with your local AWS credentials so it can call Bedrock
docker-run:
	docker run --rm -p 8080:8080 -v $(HOME)/.aws:/root/.aws:ro \
		-e AWS_PROFILE=$${AWS_PROFILE:-default} -e AWS_REGION=$${AWS_REGION:-us-east-1} \
		-e LOGFIRE_TOKEN $(IMAGE)

invoke-local:
	curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
		-d '{"question": "$(Q)"}' | python3 -m json.tool
