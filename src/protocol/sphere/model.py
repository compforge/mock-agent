from dataclasses import dataclass

from agent_model import AgentEvent, AgentInput
from protocol.sphere.schema import AgentRequest, WireEvent


@dataclass(frozen=True, kw_only=True)
class Input(AgentInput):
    # Preserve the full request for agents that use history, files, configuration,
    # or augmented context beyond the text Echo uses.
    request: AgentRequest
    bot_id: str | None = None
    rewritten_query: str | None = None


@dataclass(frozen=True)
class Event(AgentEvent):
    pass


@dataclass(frozen=True)
class TextDelta(Event):
    content: str


@dataclass(frozen=True)
class Failure(Event):
    code: str
    message: str


@dataclass(frozen=True)
class WireEventOutput(Event):
    """Emit a documented Sphere event from a custom mock agent."""

    event: WireEvent
