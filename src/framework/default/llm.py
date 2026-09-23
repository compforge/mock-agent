import logging
from collections.abc import AsyncIterator

import httpx
from httpx_sse import SSEError, aconnect_sse

from agent_model import AgentEvent, AgentInput
from protocol.sphere import model as sphere

logger = logging.getLogger(__name__)


class LLMAgent:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        model: str | None,
        api_key: str | None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._client = client
        self._model = model
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"

    def ID(self) -> str:
        return "llm"

    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        if not isinstance(input, sphere.Input):
            raise TypeError("LLMAgent requires protocol.sphere.model.Input")
        if not self._model or not self._api_key:
            yield sphere.Failure(
                code="LLM_NOT_CONFIGURED",
                message="Set OPENAI_API_KEY and OPENAI_MODEL",
            )
            return

        query = (
            input.rewritten_query
            if input.rewritten_query is not None
            else input.message
        )
        try:
            async with aconnect_sse(
                self._client,
                "POST",
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": query}],
                    "stream": True,
                },
            ) as source:
                source.response.raise_for_status()
                async for event in source.aiter_sse():
                    if event.data == "[DONE]":
                        break
                    if event.event == "error":
                        raise ValueError("LLM stream returned an error event")
                    chunk = event.json()
                    if "error" in chunk:
                        raise ValueError("LLM stream returned an error response")
                    choices = chunk.get("choices") or []
                    if choices:
                        content = choices[0].get("delta", {}).get("content")
                        if content:
                            yield sphere.TextDelta(content=content)
        except (httpx.HTTPError, SSEError, ValueError, TypeError, AttributeError):
            logger.exception(
                "LLM request failed",
                extra={"run_id": input.run_id, "model": self._model},
            )
            yield sphere.Failure(
                code="LLM_UPSTREAM_ERROR", message="LLM request failed"
            )
