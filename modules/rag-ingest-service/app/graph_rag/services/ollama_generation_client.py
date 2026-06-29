import json
import re
from time import sleep
from typing import Any

import httpx

from app.core.config import Settings


class OllamaGenerationClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.llm_base_url.rstrip("/")
        self.generate_path = "/" + settings.llm_generate_path.strip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds
        self.max_retries = settings.graph_rag_llm_max_retries
        self.retry_backoff_seconds = settings.graph_rag_llm_retry_backoff_seconds

    def generate_json(self, prompt: str, root_key: str | None = None) -> dict[str, Any]:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}{self.generate_path}", json=payload)
                    response.raise_for_status()
                data = response.json()
                raw = data.get("response")
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError("Local Mistral returned an empty response")
                return self._parse_json(raw, root_key=root_key)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                if self.retry_backoff_seconds:
                    sleep(self.retry_backoff_seconds * (attempt + 1))
        raise last_error or ValueError("Local Mistral generation failed")

    def _parse_json(self, raw: str, root_key: str | None = None) -> dict[str, Any]:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()
        parsed = self._loads_json_fragment(text)
        if not isinstance(parsed, dict):
            if root_key:
                return {root_key: parsed}
            raise ValueError(f"Local Mistral JSON response must be an object; received {type(parsed).__name__}")
        return parsed

    def _loads_json_fragment(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            candidates = [
                (text.find("{"), text.rfind("}")),
                (text.find("["), text.rfind("]")),
            ]
            valid_candidates = [(start, end) for start, end in candidates if start != -1 and end != -1 and end > start]
            if not valid_candidates:
                raise
            start, end = min(valid_candidates, key=lambda item: item[0])
            return json.loads(text[start : end + 1])
