from openai import OpenAI

from app.services.llm_providers.base import LlmProvider


class OpenAiLlmProvider(LlmProvider):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str, temperature: float, timeout_seconds: float):
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        return (response.choices[0].message.content or "").strip()
