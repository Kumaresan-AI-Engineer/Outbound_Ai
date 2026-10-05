"""Fake LLMProvider for agent tests. Returns canned ProviderResponses in order
- no real Groq/OpenAI call ever happens. Exercises the real
LLMProvider.complete_structured() parse/validate/retry logic since only
`complete()` is faked.
"""

from app.ai.providers.base import LLMProvider, ProviderResponse


class FakeLLMProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses: list[ProviderResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

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
        self.calls.append({"messages": messages, "model": model, "tools": tools})
        if not self._responses:
            raise AssertionError("FakeLLMProvider: no more canned responses queued")
        return self._responses.pop(0)
