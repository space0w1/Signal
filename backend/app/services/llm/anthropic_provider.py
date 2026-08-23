import anthropic

from app.services.llm.base import LLMProvider, LLMProviderError, T

MODEL = "claude-opus-5"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not configured")
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, prompt: str, output_schema: type[T]) -> T:
        try:
            response = self._client.messages.parse(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                output_format=output_schema,
            )
        except anthropic.AuthenticationError as exc:
            raise LLMProviderError("Invalid ANTHROPIC_API_KEY") from exc
        except anthropic.RateLimitError as exc:
            raise LLMProviderError("Rate limited by Anthropic API, try again shortly") from exc
        except anthropic.APIStatusError as exc:
            raise LLMProviderError(f"Anthropic API error: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError("Could not reach Anthropic API") from exc

        if response.parsed_output is None:
            raise LLMProviderError("Anthropic API did not return a valid structured response")
        return response.parsed_output
