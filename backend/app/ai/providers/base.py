"""Shared LLM provider abstraction.

Every agent talks to an LLM only through an `LLMProvider` instance obtained
from `app.ai.providers.factory.get_provider()` - never by instantiating a
Groq/OpenAI SDK client directly, and never by reaching into another module's
private client helpers.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ProviderResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMValidationError(RuntimeError):
    """Raised by complete_structured when the response can't be parsed/validated
    against the requested schema, even after one retry."""


def _parse_json_content(content: str | None) -> Any:
    if not content:
        raise ValueError("empty response content")
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        response_format: dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> ProviderResponse:
        """Single chat-completion call. Returns a provider-agnostic response;
        raw content plus any tool calls the model requested."""

    async def complete_structured(
        self,
        messages: list[dict],
        schema: type[T],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> T:
        """Call the model expecting a JSON object, parse it, and validate
        against `schema`. Retries once (a fresh call) on parse/validation
        failure before raising LLMValidationError."""
        last_error: Exception | None = None
        for attempt in range(2):
            response = await self.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            try:
                data = _parse_json_content(response.content)
                return schema.model_validate(data)
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as e:
                last_error = e
                logger.warning(
                    "[%s] complete_structured validation failed (attempt %d/2), schema=%s: %s",
                    self.name,
                    attempt + 1,
                    schema.__name__,
                    e,
                )
        raise LLMValidationError(f"{schema.__name__} validation failed after retry: {last_error}")

    def _log_call(self, model: str, latency_ms: int, usage: Any) -> None:
        total_tokens = getattr(usage, "total_tokens", None) if usage else None
        logger.info(
            "[LLM] provider=%s model=%s latency_ms=%d tokens=%s",
            self.name,
            model,
            latency_ms,
            total_tokens if total_tokens is not None else "n/a",
        )
