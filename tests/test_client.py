import asyncio
import json

import httpx
import pytest

from client.sphere import stream_chat
from protocol.sphere.schema import (
    AgentAugmentedContext,
    AgentChatRequest,
    AgentMessage,
    AgentRequest,
    MessagePart,
    parse_event,
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


def test_client_sends_executor_style_bare_request() -> None:
    async def check() -> None:
        request = AgentRequest(
            message=AgentMessage(role="user", parts=[MessagePart(text="original")]),
            augmented_context=AgentAugmentedContext(rewritten_query="rewritten"),
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
        assert json.loads(events[1].content)["rewritten_query"] == "rewritten"

    asyncio.run(check())


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "TASK", "task_id": "t", "task_status": "INPUT_REQUIRED"},
        {"type": "INPUT_REQUIRED_FORM", "interrupt_id": "i", "form": {"fields": []}},
        {"type": "CONTAINS_PII"},
        {"type": "DISCLAIMER", "content": "notice"},
        {"type": "HEADER", "name": "EXECUTE"},
        {"type": "STEP_THINKING", "content": True},
        {"type": "STEP_STREAM_REASONING_MESSAGE", "content": "thinking"},
        {"type": "STEP_TOOL", "tool_name": "search", "tool_status": "end"},
        {"type": "STEP_STREAM_MESSAGE", "content": "step"},
        {"type": "CARD_REGISTER_REQUEST", "card_id": "card-1"},
        {"type": "FOLLOW_UP_EXPECTED"},
        {"type": "STREAM_CARD", "card_id": "card-1", "card_data": {"k": "v"}},
        {
            "type": "REFERENCE",
            "references": [{"ref_num": 1, "content": "ref", "resource_from": "tool"}],
        },
        {"type": "AGENT_CUSTOM_MESSAGE", "custom_message_type": "test", "content": "x"},
        {"type": "OUTPUT", "parts": [{"type": "data", "data": {"ok": True}}]},
        {"type": "INCAPABLE", "code": "OUT_OF_SCOPE"},
    ],
)
def test_client_parses_documented_sphere_events(payload: dict[str, object]) -> None:
    event = parse_event(json.dumps(payload))
    assert event.type == payload["type"]
    assert event.model_dump(mode="json", exclude_none=True)["type"] == payload["type"]
