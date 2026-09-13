import logging

import httpx

from app.services.llm_providers.base import LlmProvider
from app.services.ollama_dependency import OllamaModelUnavailableError, OllamaUnavailableError


logger = logging.getLogger(__name__)


class OllamaLlmProvider(LlmProvider):
    provider_name = "ollama"

    def __init__(self, base_url: str, model: str, temperature: float, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                return str(response.json().get("response") or "").strip()
        except httpx.RequestError as exc:
            error = OllamaUnavailableError(base_url=self.base_url, model=self.model, cause=exc)
            logger.error("Ollama answer generation request failed: %s", error)
            raise error from exc
        except httpx.HTTPStatusError as exc:
            error_type = OllamaModelUnavailableError if exc.response.status_code == 404 else OllamaUnavailableError
            error = error_type(base_url=self.base_url, model=self.model, cause=exc)
            logger.error("Ollama answer generation request failed: %s", error)
            raise error from exc
