from dataclasses import dataclass

from agent_model import AgentEvent, AgentInput


@dataclass(frozen=True, kw_only=True)
class Input(AgentInput):
    bot_id: str
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
