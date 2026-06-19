from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

MODULE_ENV_FILE = Path(__file__).with_name(".env")


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Runtime settings for the Online Library NLQ agent."""

    ollama_base_url: str
    ollama_model: str
    mcp_url: str
    host: str
    port: int
    timeout_seconds: float
    default_limit: int
    tool_selection_temperature: float
    answer_temperature: float
    tool_selection_num_predict: int
    answer_num_predict: int


def load_config() -> AgentConfig:
    """Load module-local .env values so local demos are repeatable."""

    load_dotenv(MODULE_ENV_FILE, override=True)
    return AgentConfig(
        ollama_base_url=_get_env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=_get_env("OLLAMA_MODEL", "mistral:latest"),
        mcp_url=_get_env("ONLINE_LIBRARY_MCP_URL", "http://127.0.0.1:8004/mcp"),
        host=_get_env("ONLINE_LIBRARY_AGENT_HOST", "127.0.0.1"),
        port=int(_get_env("ONLINE_LIBRARY_AGENT_PORT", "8005")),
        timeout_seconds=float(_get_env("ONLINE_LIBRARY_AGENT_TIMEOUT_SECONDS", "120")),
        default_limit=int(_get_env("ONLINE_LIBRARY_AGENT_DEFAULT_LIMIT", "10")),
        tool_selection_temperature=float(_get_env("ONLINE_LIBRARY_TOOL_SELECTION_TEMPERATURE", "0.1")),
        answer_temperature=float(_get_env("ONLINE_LIBRARY_ANSWER_TEMPERATURE", "0.2")),
        tool_selection_num_predict=int(_get_env("ONLINE_LIBRARY_TOOL_SELECTION_NUM_PREDICT", "160")),
        answer_num_predict=int(_get_env("ONLINE_LIBRARY_ANSWER_NUM_PREDICT", "220")),
    )


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default
