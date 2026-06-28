import json
import re
from typing import Any

import httpx

from app.core.config import Settings


class OllamaGenerationClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.llm_base_url.rstrip("/")
        self.generate_path = "/" + settings.llm_generate_path.strip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}{self.generate_path}", json=payload)
            response.raise_for_status()
        data = response.json()
        raw = data.get("response")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Local Mistral returned an empty response")
        return self._parse_json(raw)

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Local Mistral JSON response must be an object")
        return parsed
