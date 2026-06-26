import httpx

from app.services.llm_providers.base import LlmProvider


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
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return str(response.json().get("response") or "").strip()
