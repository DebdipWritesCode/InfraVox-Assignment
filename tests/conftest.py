from __future__ import annotations

import warnings

import pytest
from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
from starlette.exceptions import StarletteDeprecationWarning

from infravox_reviewer.config import get_settings

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)


@pytest.fixture(autouse=True)
def disable_live_llm_calls(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_REVIEW", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
