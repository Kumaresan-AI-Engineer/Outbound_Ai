import time

from openai import AsyncOpenAI

from app.ai.providers.base import LLMProvider, ProviderResponse, ToolCall


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str):
        self._client = AsyncOpenAI(api_key=api_key)

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
        kwargs: dict = {}
        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._log_call(model, int((time.monotonic() - start) * 1000), getattr(response, "usage", None))

        msg = response.choices[0].message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
            for tc in (msg.tool_calls or [])
        ]
        return ProviderResponse(content=msg.content, tool_calls=tool_calls)
