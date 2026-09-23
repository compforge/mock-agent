from collections.abc import AsyncIterator
from typing import Protocol

from agent_model import AgentEvent, AgentInput


class Agent(Protocol):
    def ID(self) -> str: ...

    # Async generators expose an iterator directly; declaring async def here
    # would describe a coroutine that must be awaited before iteration.
    def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]: ...
