import asyncio

import httpx
import pytest
from cubeloop import tool
from cubeloop.providers import (
    FauxProvider,
    faux_assistant_message,
    faux_text,
    faux_thinking,
    faux_tool_call,
)
from cubeloop.providers.base import Message, Model, TextContent, UserMessage

from framework.cubeloop.agent import CubeLoopAgent
from protocol.sphere.codec import Protocol as SphereProtocol
from protocol.sphere.schema import parse_event
from server.app import create_app
from server.registry import AgentRegistry


def _app(agent: CubeLoopAgent):
    registry = AgentRegistry()
    registry.register_protocol("sphere", SphereProtocol())
    registry.register_agent(agent)
    return create_app(registry)


def _events(response: httpx.Response):
    return [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.parametrize(
    ("rewritten_query", "expected_prompt"),
    [(None, "original"), ("rewritten", "rewritten"), ("", "")],
)
def test_cubeloop_streams_and_returns_output(
    rewritten_query: str | None, expected_prompt: str
) -> None:
    async def check() -> None:
        prompts: list[str] = []
        provider = FauxProvider(provider_id="faux")

        def respond(messages: list[Message], _model: Model):
            message = messages[-1]
            assert isinstance(message, UserMessage)
            prompts.append(
                "".join(
                    part.text
                    for part in message.content
                    if isinstance(part, TextContent)
                )
            )
            return faux_assistant_message("hello world")

        provider.set_responses([respond])
        app = _app(CubeLoopAgent(provider.model("test")))
        payload: dict[str, object] = {
            "run_id": "run-1",
            "task_id": "task-1",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "original"}],
            },
        }
        if rewritten_query is not None:
            payload["augmented_context"] = {"rewritten_query": rewritten_query}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/v1/sphere/cubeloop/chat", json=payload)

        events = _events(response)
        assert response.status_code == 200
        assert prompts == [expected_prompt]
        assert events[0].type == "START"
        assert events[-2].type == "OUTPUT"
        assert events[-2].parts[0].text == "hello world"
        assert events[-1].type == "END"
        assert (
            "".join(event.content for event in events if event.type == "STREAM_MESSAGE")
            == "hello world"
        )
        assert all(event.run_id == "run-1" for event in events)
        assert all(event.task_id == "task-1" for event in events)

    asyncio.run(check())


def test_cubeloop_provider_error_becomes_sphere_error() -> None:
    async def check() -> None:
        provider = FauxProvider(provider_id="faux")
        provider.set_responses(
            [faux_assistant_message("", stop_reason="error", error_message="secret")]
        )
        app = _app(CubeLoopAgent(provider.model("test")))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/v1/sphere/cubeloop/chat",
                json={
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": "hi"}],
                    }
                },
            )

        events = _events(response)
        assert [event.type for event in events] == ["START", "ERROR", "END"]
        assert events[1].error_code == "CUBELOOP_UPSTREAM_ERROR"
        assert "secret" not in response.text

    asyncio.run(check())


def test_cubeloop_reasoning_and_tool_events_use_sphere_types() -> None:
    @tool
    async def echo(value: str) -> str:
        """Return the supplied value."""
        return value

    async def check() -> None:
        provider = FauxProvider(provider_id="faux")
        provider.set_responses(
            [
                faux_assistant_message(
                    [
                        faux_thinking("Use the echo tool."),
                        faux_tool_call("echo", {"value": "result"}, id="tool-1"),
                    ],
                    stop_reason="tool_use",
                ),
                faux_assistant_message([faux_thinking("Done."), faux_text("final")]),
            ]
        )
        app = _app(CubeLoopAgent(provider.model("test"), tools=[echo]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/v1/sphere/cubeloop/chat",
                json={
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": "hi"}],
                    }
                },
            )

        events = _events(response)
        assert response.status_code == 200
        assert [
            event.thinking_status for event in events if event.type == "STEP_THINKING"
        ] == ["start", "end", "start", "end"]
        assert (
            "".join(
                event.content
                for event in events
                if event.type == "STEP_STREAM_REASONING_MESSAGE"
            )
            == "Use the echo tool.Done."
        )
        tools = [event for event in events if event.type == "STEP_TOOL"]
        assert [
            (event.tool_name, event.tool_status, event.tool_call_id) for event in tools
        ] == [
            ("echo", "start", "tool-1"),
            ("echo", "end", "tool-1"),
        ]
        assert tools[0].tool_input == '{"value": "result"}'
        assert "result" in tools[1].tool_content
        assert [event.parts[0].text for event in events if event.type == "OUTPUT"] == [
            "final"
        ]
        assert (
            "".join(event.content for event in events if event.type == "STREAM_MESSAGE")
            == "final"
        )
        assert events[-1].type == "END"

    asyncio.run(check())


def test_cubeloop_without_configuration_returns_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/sphere/cubeloop/chat",
            json={
                "message": {"role": "user", "parts": [{"type": "text", "text": "hi"}]}
            },
        )

    events = _events(response)
    assert [event.type for event in events] == ["START", "ERROR", "END"]
    assert events[1].error_code == "CUBELOOP_NOT_CONFIGURED"
