"""Built-in Sphere event example; available at /v1/sphere/demo/chat."""

from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentInput
from framework.base import AgentConfig
from protocol.sphere.model import Input, TextDelta, WireEventOutput
from protocol.sphere.schema import (
    DataPart,
    HeaderEvent,
    OutputEvent,
    StepStreamMessageEvent,
    StepToolEvent,
    TaskEvent,
    TextPart,
)


class SphereDemoAgent:
    def ID(self) -> str:
        return "demo"

    def protocol(self) -> str:
        return "sphere"

    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        if not isinstance(input, Input):
            raise TypeError("SphereDemoAgent requires a Sphere request")

        if input.task_id:
            yield WireEventOutput(
                TaskEvent(task_id=input.task_id, task_status="WORKING")
            )
        yield WireEventOutput(HeaderEvent(name="EXECUTE"))
        yield WireEventOutput(
            StepToolEvent(tool_name="example_tool", tool_status="start")
        )
        yield WireEventOutput(
            StepToolEvent(tool_name="example_tool", tool_status="end")
        )
        yield WireEventOutput(StepStreamMessageEvent(content="Preparing answer"))
        yield TextDelta(content=input.message)
        # OUTPUT is the durable handoff result; STREAM_MESSAGE is display text.
        yield WireEventOutput(
            OutputEvent(
                parts=[
                    TextPart(text=input.message),
                    DataPart(data={"rewritten_query": input.rewritten_query}),
                ]
            )
        )
        if input.task_id:
            yield WireEventOutput(
                TaskEvent(task_id=input.task_id, task_status="COMPLETED")
            )


class SphereDemoAgentBuilder:
    def build(self, config: AgentConfig) -> SphereDemoAgent:
        return SphereDemoAgent()
