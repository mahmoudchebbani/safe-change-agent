import pytest

from safe_change_agent.config import get_model


def test_openai_is_default(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    assert get_model() == "openai:gpt-4.1-mini"


def test_bedrock(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL", "some-model")
    assert get_model() == "bedrock:some-model"


def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "nope")
    with pytest.raises(ValueError):
        get_model()
