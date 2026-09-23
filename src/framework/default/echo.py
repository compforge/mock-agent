import json
from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentInput
from protocol.sphere import model as sphere


class EchoAgent:
    def ID(self) -> str:
        return "echo"

    def protocol(self) -> str:
        return "sphere"

    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        if not isinstance(input, sphere.Input):
            raise TypeError("EchoAgent requires protocol.sphere.model.Input")
        if input.rewritten_query is None:
            yield sphere.TextDelta(content=input.message)
            return

        yield sphere.TextDelta(
            content=json.dumps(
                {"message": input.message, "rewritten_query": input.rewritten_query},
                ensure_ascii=False,
            )
        )
