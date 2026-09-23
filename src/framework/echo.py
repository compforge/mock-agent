from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentInput, TextDelta


class EchoAgent:
    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        yield TextDelta(content=input.message)
