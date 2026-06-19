from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

MODULE_ENV_FILE = Path(__file__).with_name(".env")


@dataclass(frozen=True, slots=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None


def load_llm_config() -> LLMConfig:
    load_dotenv(MODULE_ENV_FILE, override=True)

    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider == "ollama":
        return LLMConfig(
            provider="ollama",
            model=_normalize_ollama_model(_get_required_env("OLLAMA_MODEL")),
            api_key=_get_optional_env("OLLAMA_API_KEY"),
            base_url=_get_required_env("OLLAMA_BASE_URL"),
        )
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER '{provider}'. Use 'gemini' or 'ollama'.")

    api_key = _get_required_env("GEMINI_API_KEY").strip('"').strip("'")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Set it in your shell, or set LLM_PROVIDER=ollama."
        )
    if api_key in {"add-your-gemini-api-key-here", "your-gemini-api-key"}:
        raise RuntimeError(
            "GEMINI_API_KEY still contains the placeholder value. Replace it with a valid Gemini API key."
        )

    return LLMConfig(
        provider="gemini",
        api_key=api_key,
        model=_normalize_gemini_model(_get_required_env("GEMINI_MODEL")),
    )


def _normalize_gemini_model(model: str) -> str:
    if model.startswith("gemini/"):
        return model.removeprefix("gemini/")
    return model


def _normalize_ollama_model(model: str) -> str:
    if model.startswith("ollama/"):
        return model.removeprefix("ollama/")
    return model


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not configured. Set it in modules/weather_ai_agent/.env or your shell."
        )
    return value


def _get_optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
