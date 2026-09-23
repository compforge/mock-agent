import json
from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentInput, TextDelta


class EchoAgent:
    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        if input.rewritten_query is None:
            yield TextDelta(content=input.message)
            return

        yield TextDelta(
            content=json.dumps(
                {"message": input.message, "rewritten_query": input.rewritten_query},
                ensure_ascii=False,
            )
        )
