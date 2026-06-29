import httpx

from app.services.llm_providers.base import LlmProvider


class GeminiLlmProvider(LlmProvider):
    provider_name = "gemini"

    def __init__(self, api_key: str, base_url: str, model: str, temperature: float, timeout_seconds: float):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
            },
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            return _extract_text(response.json()).strip()


def _extract_text(payload: dict) -> str:
    parts = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                parts.append(str(text))
    return "\n".join(parts)
