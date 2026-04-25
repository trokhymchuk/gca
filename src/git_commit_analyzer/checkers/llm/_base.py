from abc import ABC, abstractmethod


class LlmBackend(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int, stop: list[str]) -> str:
        """Run inference on *prompt* and return the raw generated text."""
