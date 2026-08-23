from google import genai
from google.genai import errors, types

from app.services.llm.base import LLMProvider, LLMProviderError, T


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMProviderError("GEMINI_API_KEY is not configured")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, output_schema: type[T]) -> T:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=output_schema,
                ),
            )
        except errors.ClientError as exc:
            raise LLMProviderError(f"Gemini API error ({exc.status}): {exc.message}") from exc
        except errors.ServerError as exc:
            raise LLMProviderError(f"Gemini server error ({exc.status}): {exc.message}") from exc
        except errors.APIError as exc:
            raise LLMProviderError(f"Gemini API error: {exc.message}") from exc

        if response.parsed is None:
            raise LLMProviderError("Gemini API did not return a valid structured response")
        return response.parsed
