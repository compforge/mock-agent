import asyncio
import json
import logging
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi.testclient import TestClient

from agent_model import AgentEvent, AgentInput
from framework.base import Agent, AgentConfig
from framework.default.echo import EchoAgent, EchoAgentBuilder
from framework.default.llm import LLMAgent, LLMAgentBuilder
from protocol.sphere.codec import Protocol as SphereProtocol
from protocol.sphere.model import Failure, Input, WireEventOutput
from protocol.sphere.schema import (
    DataPart,
    FollowUpExpectedEvent,
    OutputEvent,
    Reference,
    ReferenceEvent,
    StepToolEvent,
    TaskEvent,
    TextPart,
    parse_event,
)
from server.app import create_app
from server.registry import AgentRegistry


def _request(
    message: str = "hello", rewritten_query: str | None = None, bot_id: str = "echo"
) -> dict[str, object]:
    agent_request = {
        "run_id": "run-1",
        "task_id": "task-1",
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": message}],
        },
    }
    if rewritten_query is not None:
        agent_request["augmented_context"] = {"rewritten_query": rewritten_query}
    return {"bot_id": bot_id, "agent_request": agent_request}


def _registry(*agents: Agent) -> AgentRegistry:
    registry = AgentRegistry()
    registry.register_protocol("sphere", SphereProtocol())
    for agent in agents:
        registry.register_agent(agent)
    return registry


def test_echo_stream() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/sphere/echo/chat", json=_request())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == ["START", "STREAM_MESSAGE", "END"]
    assert events[1].content == "hello"
    assert all(event.run_id == "run-1" for event in events)
    assert all(event.task_id == "task-1" for event in events)


def test_executor_bare_request_preserves_sphere_context() -> None:
    class InspectAgent:
        def ID(self) -> str:
            return "inspect"

        def protocol(self) -> str:
            return "sphere"

        async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
            assert isinstance(input, Input)
            assert input.bot_id is None
            assert input.request.context_id == "context-1"
            assert input.request.augmented_context is not None
            assert input.request.augmented_context.rewritten_query == "rewritten"
            assert input.request.history is not None
            assert input.request.history[0].meta_data == {"generated_by_me": True}
            assert input.request.message.parts[1].type == "file"
            assert input.request.message.parts[2].type == "data"
            assert input.request.configuration is not None
            assert input.request.configuration.execution_mode == "sub_agent"
            assert input.request.meta_data == {"customer_option": "value"}
            yield WireEventOutput(
                TaskEvent(task_id=input.task_id or "", task_status="WORKING")
            )
            yield WireEventOutput(
                StepToolEvent(tool_name="mock_tool", tool_status="start")
            )
            yield WireEventOutput(
                ReferenceEvent(
                    references=[
                        Reference(
                            ref_num=1,
                            content="source",
                            resource_from="web",
                            title="Example",
                            url="https://example.com",
                        )
                    ]
                )
            )
            yield WireEventOutput(
                OutputEvent(parts=[TextPart(text="done"), DataPart(data={"ok": True})])
            )
            yield WireEventOutput(FollowUpExpectedEvent())

    payload = {
        "run_id": "run-1",
        "task_id": "task-1",
        "context_id": "context-1",
        "augmented_context": {
            "rewritten_query": "rewritten",
            "contains_pii": True,
            "topic_control": {"labels": ["support"]},
        },
        "history": [
            {
                "role": "assistant",
                "parts": [{"type": "text", "text": "earlier"}],
                "meta_data": {"generated_by_me": True},
            }
        ],
        "message": {
            "role": "user",
            "parts": [
                {"type": "text", "text": "original"},
                {
                    "type": "file",
                    "file": {"kind": "bytes", "name": "a.txt", "bytes": "YQ=="},
                },
                {"type": "data", "data": {"source": "test"}},
            ],
        },
        "configuration": {"execution_mode": "sub_agent", "deep_mode": True},
        "meta_data": {"customer_option": "value"},
    }
    with TestClient(create_app(_registry(InspectAgent()))) as client:
        response = client.post("/v1/sphere/inspect/chat", json=payload)

    assert response.status_code == 200
    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == [
        "START",
        "TASK",
        "STEP_TOOL",
        "REFERENCE",
        "OUTPUT",
        "FOLLOW_UP_EXPECTED",
        "END",
    ]
    assert all(event.run_id == "run-1" for event in events)
    assert all(event.task_id == "task-1" for event in events)
    assert events[4].parts[1].data == {"ok": True}


@pytest.mark.parametrize("rewritten_query", [None, "", "rewritten"])
def test_bare_request_echo_and_rewrite_log(
    caplog: pytest.LogCaptureFixture, rewritten_query: str | None
) -> None:
    payload = _request(message="original")["agent_request"]
    assert isinstance(payload, dict)
    if rewritten_query is not None:
        payload["augmented_context"] = {"rewritten_query": rewritten_query}
    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        TestClient(create_app()) as client,
    ):
        response = client.post("/v1/sphere/echo/chat", json=payload)

    assert response.status_code == 200
    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    expected = (
        "original"
        if rewritten_query is None
        else json.dumps(
            {"message": "original", "rewritten_query": rewritten_query},
            ensure_ascii=False,
        )
    )
    assert events[1].content == expected
    receipt = next(
        record.getMessage()
        for record in caplog.records
        if "sphere request received" in record.getMessage()
    )
    assert "bot_id=None" in receipt
    assert (
        f"rewritten_query_status={'missing' if rewritten_query is None else 'empty' if rewritten_query == '' else 'present'}"
        in receipt
    )


@pytest.mark.parametrize("rewritten_query", ["改写后的问题", ""])
def test_rewritten_query_reaches_agent(rewritten_query: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/sphere/echo/chat", json=_request("原始问题", rewritten_query)
        )

    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == ["START", "STREAM_MESSAGE", "END"]
    assert json.loads(events[1].content) == {
        "message": "原始问题",
        "rewritten_query": rewritten_query,
    }


@pytest.mark.parametrize(
    ("augmented_context", "expected_status"),
    [
        (None, "missing"),
        ({}, "missing"),
        ({"rewritten_query": None}, "null"),
        ({"rewritten_query": ""}, "empty"),
        ({"rewritten_query": "private rewrite", "contains_pii": True}, "present"),
    ],
)
def test_request_log_records_rewrite_status_without_content(
    caplog: pytest.LogCaptureFixture,
    augmented_context: dict[str, object] | None,
    expected_status: str,
) -> None:
    payload = _request(message="private original")
    agent_request = payload["agent_request"]
    assert isinstance(agent_request, dict)
    agent_request["context_id"] = "context-1"
    if augmented_context is not None:
        agent_request["augmented_context"] = augmented_context

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        TestClient(create_app()) as client,
    ):
        response = client.post("/v1/sphere/echo/chat", json=payload)

    assert response.status_code == 200
    receipt_logs = [
        record.getMessage()
        for record in caplog.records
        if "sphere request received" in record.getMessage()
    ]
    assert len(receipt_logs) == 1
    assert (
        "bot_id='echo' context_id='context-1' run_id='run-1' task_id='task-1'"
        in receipt_logs[0]
    )
    assert f"rewritten_query_status={expected_status}" in receipt_logs[0]
    assert (
        f"contains_pii={bool(augmented_context and augmented_context.get('contains_pii'))}"
        in receipt_logs[0]
    )
    assert "private original" not in receipt_logs[0]
    assert "private rewrite" not in receipt_logs[0]


def test_request_log_escapes_control_characters_in_identifiers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    injected = "\nINFO: sphere request received rewritten_query_status=present\x1b[2J"
    payload = _request(bot_id=f"echo{injected}")
    agent_request = payload["agent_request"]
    assert isinstance(agent_request, dict)
    agent_request["context_id"] = f"context{injected}"
    agent_request["run_id"] = f"run{injected}"
    agent_request["task_id"] = f"task{injected}"

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        TestClient(create_app()) as client,
    ):
        response = client.post("/v1/sphere/echo/chat", json=payload)

    assert response.status_code == 200
    receipt_logs = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("sphere request received")
    ]
    assert len(receipt_logs) == 1
    receipt = receipt_logs[0]
    assert len(receipt.splitlines()) == 1
    assert "\x1b" not in receipt
    for identifier in (
        payload["bot_id"],
        *(agent_request[key] for key in ("context_id", "run_id", "task_id")),
    ):
        assert repr(identifier) in receipt


@pytest.mark.parametrize(
    ("rewritten_query", "expected_query"),
    [(None, "original"), ("rewritten", "rewritten")],
)
def test_llm_agent_streams_one_upstream_request(
    rewritten_query: str | None, expected_query: str
) -> None:
    async def check() -> None:
        requests: list[httpx.Request] = []

        def upstream(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=(
                    'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
                    'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
                    "data: [DONE]\n\n"
                ),
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(upstream)
        ) as llm_client:
            app = create_app(
                _registry(
                    EchoAgent(),
                    LLMAgentBuilder(llm_client).build(
                        AgentConfig(
                            model="test-model",
                            api_key="test-key",
                            base_url="https://llm.example/v1",
                        )
                    ),
                )
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.post(
                    "/v1/sphere/llm/chat",
                    json=_request("original", rewritten_query, bot_id="llm"),
                )

        events = [
            parse_event(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert [event.type for event in events] == [
            "START",
            "STREAM_MESSAGE",
            "STREAM_MESSAGE",
            "END",
        ]
        assert [event.content for event in events[1:3]] == ["hello", " world"]
        assert len(requests) == 1
        assert requests[0].url == "https://llm.example/v1/chat/completions"
        assert requests[0].headers["authorization"] == "Bearer test-key"
        assert json.loads(requests[0].content) == {
            "model": "test-model",
            "messages": [{"role": "user", "content": expected_query}],
            "stream": True,
        }

    asyncio.run(check())


def test_llm_agent_without_configuration_returns_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with TestClient(create_app()) as client:
        response = client.post("/v1/sphere/llm/chat", json=_request(bot_id="llm"))

    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == ["START", "ERROR", "END"]
    assert events[1].error_code == "LLM_NOT_CONFIGURED"


def test_llm_upstream_http_error_becomes_terminal_event() -> None:
    async def check() -> None:
        def upstream(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(upstream)
        ) as llm_client:
            app = create_app(
                _registry(LLMAgent(llm_client, model="test-model", api_key="test-key"))
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.post(
                    "/v1/sphere/llm/chat", json=_request(bot_id="llm")
                )

        events = [
            parse_event(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert [event.type for event in events] == ["START", "ERROR", "END"]
        assert events[1].error_code == "LLM_UPSTREAM_ERROR"

    asyncio.run(check())


def test_invalid_request() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/sphere/echo/chat", json={"bot_id": "echo"})

    assert response.status_code == 422


class FailingAgent:
    def ID(self) -> str:
        return "failing"

    def protocol(self) -> str:
        return "sphere"

    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        yield Failure(code="EXPECTED_FAILURE", message="Expected failure")


def test_agent_error_is_a_terminal_sse_event() -> None:
    with TestClient(create_app(_registry(EchoAgent(), FailingAgent()))) as client:
        response = client.post("/v1/sphere/failing/chat", json=_request())
        echo_response = client.post("/v1/sphere/echo/chat", json=_request())

    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == ["START", "ERROR", "END"]
    assert events[1].error_code == "EXPECTED_FAILURE"
    echo_events = [
        parse_event(line.removeprefix("data: "))
        for line in echo_response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert echo_events[1].content == "hello"


@pytest.mark.parametrize(
    "path",
    [
        "/v1/unknown/echo/chat",
        "/v1/sphere/unknown/chat",
        "/v1/sphere/default/echo/chat",
    ],
)
def test_unknown_binding(path: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(path, json=_request())

    assert response.status_code == 404


def test_agent_protocol_must_be_registered() -> None:
    class OtherProtocolAgent(EchoAgent):
        def protocol(self) -> str:
            return "other"

    with pytest.raises(ValueError, match="Register protocol 'other'"):
        _registry(OtherProtocolAgent())


def test_duplicate_agent_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):
        _registry(EchoAgent(), EchoAgent())


def test_echo_builder_creates_supported_agent() -> None:
    agent = EchoAgentBuilder().build(
        AgentConfig(model=None, api_key=None, base_url="https://api.openai.com/v1")
    )
    assert agent.ID() == "echo"
    assert agent.protocol() == "sphere"
