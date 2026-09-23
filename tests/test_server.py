import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from agent_model import AgentEvent, AgentFailure, AgentInput
from framework.default.echo import EchoAgent
from protocol.sphere.schema import parse_event
from server.app import create_app


def _request(
    message: str = "hello", rewritten_query: str | None = None
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
    return {"bot_id": "echo", "agent_request": agent_request}


def test_echo_stream() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/sphere/default/echo/chat", json=_request())

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


@pytest.mark.parametrize("rewritten_query", ["改写后的问题", ""])
def test_rewritten_query_reaches_agent(rewritten_query: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/sphere/default/echo/chat", json=_request("原始问题", rewritten_query)
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


def test_invalid_request() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/sphere/default/echo/chat", json={"bot_id": "echo"})

    assert response.status_code == 422


class FailingAgent:
    def ID(self) -> str:
        return "failing"

    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        yield AgentFailure(code="EXPECTED_FAILURE", message="Expected failure")


def test_agent_error_is_a_terminal_sse_event() -> None:
    with TestClient(
        create_app(frameworks={"default": (EchoAgent(), FailingAgent())})
    ) as client:
        response = client.post("/v1/sphere/default/failing/chat", json=_request())
        echo_response = client.post("/v1/sphere/default/echo/chat", json=_request())

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
        "/v1/unknown/default/echo/chat",
        "/v1/sphere/unknown/echo/chat",
        "/v1/sphere/default/unknown/chat",
    ],
)
def test_unknown_binding(path: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(path, json=_request())

    assert response.status_code == 404
