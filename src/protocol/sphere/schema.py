from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class MessagePart(BaseModel):
    type: str
    text: str | None = None


class AgentMessage(BaseModel):
    role: str
    parts: list[MessagePart] = Field(min_length=1)


class AgentAugmentedContext(BaseModel):
    contains_pii: bool = False
    rewritten_query: str | None = None


class AgentRequest(BaseModel):
    message: AgentMessage
    run_id: str | None = None
    context_id: str | None = None
    task_id: str | None = None
    augmented_context: AgentAugmentedContext | None = None


class AgentChatRequest(BaseModel):
    bot_id: str
    agent_request: AgentRequest


class _Event(BaseModel):
    run_id: str | None = None
    task_id: str | None = None


class StartEvent(_Event):
    type: Literal["START"] = "START"


class StreamMessageEvent(_Event):
    type: Literal["STREAM_MESSAGE"] = "STREAM_MESSAGE"
    content: str


class ErrorEvent(_Event):
    type: Literal["ERROR"] = "ERROR"
    error_code: str
    error_message: str


class EndEvent(_Event):
    type: Literal["END"] = "END"
    suggest_question: bool = False


WireEvent = StartEvent | StreamMessageEvent | ErrorEvent | EndEvent
_event_adapter = TypeAdapter(Annotated[WireEvent, Field(discriminator="type")])


def parse_event(data: str) -> WireEvent:
    return _event_adapter.validate_json(data)
