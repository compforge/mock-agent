from collections.abc import AsyncIterator, Mapping

import httpx
from httpx_sse import aconnect_sse

from protocol.sphere.schema import AgentChatRequest, SphereEvent, parse_event


async def stream_chat(
    client: httpx.AsyncClient,
    url: str,
    request: AgentChatRequest,
    headers: Mapping[str, str] | None = None,
) -> AsyncIterator[SphereEvent]:
    """Stream Sphere events from an HTTP agent endpoint."""
    async with aconnect_sse(
        client,
        "POST",
        url,
        json=request.model_dump(mode="json", exclude_none=True),
        headers=dict(headers or {}),
    ) as source:
        source.response.raise_for_status()
        async for event in source.aiter_sse():
            yield parse_event(event.data)
