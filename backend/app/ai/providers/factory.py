"""The only place in the codebase that decides Groq vs OpenAI."""

from functools import lru_cache

from app.ai.providers.base import LLMProvider
from app.ai.providers.groq_provider import GroqProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.config import get_settings


@lru_cache
def _groq_provider() -> GroqProvider:
    return GroqProvider(api_key=get_settings().groq_api_key)


@lru_cache
def _openai_provider() -> OpenAIProvider:
    return OpenAIProvider(api_key=get_settings().openai_api_key)


def get_provider(name: str | None = None) -> LLMProvider:
    """Resolve an LLMProvider by name, defaulting to settings.ai_provider."""
    name = name or get_settings().ai_provider
    if name == "groq":
        return _groq_provider()
    if name == "openai":
        return _openai_provider()
    raise ValueError(f"Unknown AI provider: {name!r}")
