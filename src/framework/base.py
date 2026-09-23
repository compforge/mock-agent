from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from agent_model import AgentEvent, AgentInput


class Agent(Protocol):
    def ID(self) -> str: ...

    def protocol(self) -> str: ...

    # Async generators expose an iterator directly; declaring async def here
    # would describe a coroutine that must be awaited before iteration.
    def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]: ...


@dataclass(frozen=True)
class AgentConfig:
    model: str | None
    api_key: str | None
    base_url: str


class AgentBuilder(Protocol):
    def build(self, config: AgentConfig) -> Agent: ...
