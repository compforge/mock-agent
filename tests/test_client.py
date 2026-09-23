import asyncio
import json

import httpx

from client.sphere import stream_chat
from protocol.sphere.schema import (
    AgentAugmentedContext,
    AgentChatRequest,
    AgentMessage,
    AgentRequest,
    MessagePart,
)
from server.app import create_app


def test_client_reads_the_server_stream() -> None:
    async def check() -> None:
        request = AgentChatRequest(
            bot_id="echo",
            agent_request=AgentRequest(
                message=AgentMessage(
                    role="user", parts=[MessagePart(type="text", text="from client")]
                ),
                augmented_context=AgentAugmentedContext(rewritten_query="rewritten"),
            ),
        )
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            events = [
                event
                async for event in stream_chat(client, "/v1/sphere/echo/chat", request)
            ]

        assert [event.type for event in events] == ["START", "STREAM_MESSAGE", "END"]
        assert json.loads(events[1].content) == {
            "message": "from client",
            "rewritten_query": "rewritten",
        }

    asyncio.run(check())
