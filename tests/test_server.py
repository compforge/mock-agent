from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from agent_model import AgentEvent, AgentFailure, AgentInput
from protocol.agentsphere.schema import parse_event
from server.app import create_app


def _request(message: str = "hello") -> dict[str, object]:
    return {
        "bot_id": "echo",
        "agent_request": {
            "run_id": "run-1",
            "task_id": "task-1",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": message}],
            },
        },
    }


def test_echo_stream() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/chats", json=_request())

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


def test_invalid_request() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/chats", json={"bot_id": "echo"})

    assert response.status_code == 422


class FailingAgent:
    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        yield AgentFailure(code="EXPECTED_FAILURE", message="Expected failure")


def test_agent_error_is_a_terminal_sse_event() -> None:
    with TestClient(create_app(agent=FailingAgent())) as client:
        response = client.post("/api/v1/chats", json=_request())

    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == ["START", "ERROR", "END"]
    assert events[1].error_code == "EXPECTED_FAILURE"
