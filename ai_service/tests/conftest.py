import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.llm.client import LLMClient


@pytest.fixture(scope="session")
def llm():
    """Real LLM client from .env. Raises ValueError if provider, key or model is missing."""
    return LLMClient.from_settings(settings)