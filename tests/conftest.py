import os

import dotenv
import pytest

from safe_change_agent.agent import create_agent
from safe_change_agent.data import DEFAULT_REPO_DIR
from safe_change_agent.tools import create_codebase_tools

dotenv.load_dotenv()


@pytest.fixture(scope="module")
def tools():
    if not DEFAULT_REPO_DIR.is_dir():
        pytest.skip("target repo missing, run `make targets` first")
    return create_codebase_tools()


@pytest.fixture(scope="module")
def agent(tools):
    if not os.getenv("OPENAI_API_KEY") and os.getenv("MODEL_PROVIDER", "openai") == "openai":
        pytest.skip("OPENAI_API_KEY not set")
    return create_agent(tools)
