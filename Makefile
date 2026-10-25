.PHONY: setup targets test

setup:
	uv sync

targets:
	./scripts/fetch_targets.sh

test:
	uv run pytest
