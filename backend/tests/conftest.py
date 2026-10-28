import os

# Set before the app is imported so LangSmith never tries to send traces.
os.environ["LANGSMITH_TRACING"] = "false"

import pytest  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
