from app.core.config import settings
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import LLMProvider, LLMProviderError
from app.services.llm.gemini_provider import GeminiProvider

_PROVIDERS = {"anthropic", "gemini"}


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider(settings.anthropic_api_key)
    if provider == "gemini":
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    raise LLMProviderError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}' (expected one of {sorted(_PROVIDERS)})"
    )


__all__ = ["LLMProvider", "LLMProviderError", "get_llm_provider"]
