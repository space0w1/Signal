from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, output_schema: type[T]) -> T:
        """Calls the LLM with prompt, returns a validated instance of output_schema."""
