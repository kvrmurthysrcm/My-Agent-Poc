from abc import ABC, abstractmethod


class LlmProvider(ABC):
    provider_name: str
    model: str

    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError
