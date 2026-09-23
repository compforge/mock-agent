from collections.abc import AsyncIterator
from typing import Protocol

from agent_model import AgentEvent, AgentInput


class AgentProtocol(Protocol):
    def decode_request(self, payload: object) -> AgentInput: ...

    def encode_stream(
        self, input: AgentInput, events: AsyncIterator[AgentEvent]
    ) -> AsyncIterator[str]: ...
