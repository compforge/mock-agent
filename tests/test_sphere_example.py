from fastapi.testclient import TestClient

from protocol.sphere.schema import parse_event
from server.app import create_app


def test_runnable_sphere_example_emits_handoff_output() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/sphere/demo/chat",
            json={
                "run_id": "run-1",
                "task_id": "task-1",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "hello"}],
                },
                "augmented_context": {"rewritten_query": "hello, clarified"},
            },
        )

    assert response.status_code == 200
    events = [
        parse_event(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event.type for event in events] == [
        "START",
        "TASK",
        "HEADER",
        "STEP_TOOL",
        "STEP_TOOL",
        "STEP_STREAM_MESSAGE",
        "STREAM_MESSAGE",
        "OUTPUT",
        "TASK",
        "END",
    ]
    assert events[7].parts[1].data == {"rewritten_query": "hello, clarified"}
