from __future__ import annotations

import json
from typing import Any

import httpx

from .config import AgentConfig, load_config
from .trace_context import outbound_trace_headers


class OllamaClient:
    """Minimal Ollama client for local model generation."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or load_config()

    async def generate(self, prompt: str, temperature: float, num_predict: int) -> str:
        """Call Ollama /api/generate and return the generated text."""

        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(
                f"{self.config.ollama_base_url}/api/generate",
                json=payload,
                headers=outbound_trace_headers(),
            )
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", "")).strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse an LLM JSON object even if the model adds surrounding text."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
