from dataclasses import dataclass


# Keyword-only shared fields let protocol inputs add required fields.
@dataclass(frozen=True, kw_only=True)
class AgentInput:
    message: str
    run_id: str | None = None
    task_id: str | None = None


@dataclass(frozen=True)
class AgentEvent:
    pass
