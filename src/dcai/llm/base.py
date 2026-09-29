from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float | None = None


class LLMProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse: ...
