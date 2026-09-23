from dataclasses import dataclass


@dataclass(frozen=True)
class AgentInput:
    message: str
    run_id: str | None = None
    task_id: str | None = None
    rewritten_query: str | None = None


@dataclass(frozen=True)
class TextDelta:
    content: str


@dataclass(frozen=True)
class AgentFailure:
    code: str
    message: str


AgentEvent = TextDelta | AgentFailure
