"""Public Sphere request and SSE shapes, without a private SDK dependency."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class SphereModel(BaseModel):
    # Keep extension fields available to example agents and newer clients.
    model_config = ConfigDict(extra="allow")


class TextPart(SphereModel):
    type: Literal["text"] = "text"
    text: str


MessagePart = TextPart  # Name used by existing sample clients.


class DataPart(SphereModel):
    type: Literal["data"] = "data"
    data: dict[str, Any]


class FileWithBytes(SphereModel):
    kind: Literal["bytes"] = "bytes"
    bytes: str  # Base64 in JSON.
    name: str | None = None
    mime_type: str | None = None


class FileWithResource(SphereModel):
    kind: Literal["resource"] = "resource"
    resource_id: str
    resource_type: Literal["file", "image"]
    name: str | None = None
    mime_type: str | None = None
    document_meta: dict[str, Any] | None = None


class FileWithUrl(SphereModel):
    kind: Literal["url"] = "url"
    url: str
    name: str | None = None
    mime_type: str | None = None
    expires_at: int | None = None


class FileWithText(SphereModel):
    kind: Literal["text"] = "text"
    text: str
    name: str | None = None
    mime_type: str | None = None


class FileWithArtifact(SphereModel):
    kind: Literal["artifact"] = "artifact"
    artifact_id: str
    name: str | None = None
    mime_type: str | None = None


FileObject = Annotated[
    FileWithBytes | FileWithResource | FileWithUrl | FileWithText | FileWithArtifact,
    Field(discriminator="kind"),
]


class FilePart(SphereModel):
    type: Literal["file"] = "file"
    file: FileObject


MessageContent = Annotated[TextPart | FilePart | DataPart, Field(discriminator="type")]
OutputContent = Annotated[TextPart | DataPart, Field(discriminator="type")]


class AgentMessage(SphereModel):
    role: Literal["user", "assistant", "system"]
    parts: list[MessageContent] = Field(min_length=1)
    timestamp: int | None = None
    message_id: str | None = None
    conversation_id: str | None = None
    meta_data: dict[str, Any] | None = None


class TopicControl(SphereModel):
    labels: list[str] | None = None
    soft_reply_prompt: str | None = None


class EmotionDetection(SphereModel):
    emotion_type: str | None = None
    comfort_direction: str | None = None
    comfort_reference: str | None = None
    scenario_id: int = -1


class AgentAugmentedContext(SphereModel):
    persona: str | None = None
    topic_control: TopicControl | None = None
    emotion_detection: EmotionDetection | None = None
    long_term_memory: str | None = None
    short_term_memory: str | None = None
    interrupt_resumes: dict[str, Any] | None = None
    contains_pii: bool = False
    rewritten_query: str | None = None
    subtext: str | None = None
    user_preference: dict[str, Any] | None = None


class AgentConfiguration(SphereModel):
    deep_mode: bool = False
    execution_mode: Literal["normal", "sub_agent", "handoff"] = "normal"
    enable_agent_custom_message: bool = True
    enable_message: bool = True


class AgentRequest(SphereModel):
    message: AgentMessage
    run_id: str | None = None
    context_id: str | None = None
    task_id: str | None = None
    augmented_context: AgentAugmentedContext | None = None
    history: list[AgentMessage] | None = None
    configuration: AgentConfiguration | None = None
    request_headers: dict[str, str] | None = None
    meta_data: dict[str, Any] | None = None


class AgentChatRequest(SphereModel):
    """Legacy wrapper; Executor sends the bare AgentRequest instead."""

    bot_id: str
    agent_request: AgentRequest


class _Event(SphereModel):
    run_id: str | None = None
    event_id: str | None = None
    task_id: str | None = None
    emit_agent_id: str | None = None
    meta_data: dict[str, Any] | None = None


class StartEvent(_Event):
    type: Literal["START"] = "START"


class TaskEvent(_Event):
    type: Literal["TASK"] = "TASK"
    task_id: str
    task_status: Literal[
        "SUBMITTED", "INPUT_REQUIRED", "COMPLETED", "WORKING", "CANCELED", "FAILED"
    ]


class InputRequiredFormEvent(_Event):
    type: Literal["INPUT_REQUIRED_FORM"] = "INPUT_REQUIRED_FORM"
    interrupt_id: str
    form: dict[str, Any]
    purpose: str | None = None


class ContainsPIIEvent(_Event):
    type: Literal["CONTAINS_PII"] = "CONTAINS_PII"


class DisclaimerEvent(_Event):
    type: Literal["DISCLAIMER"] = "DISCLAIMER"
    content: str


class HeaderEvent(_Event):
    type: Literal["HEADER"] = "HEADER"
    name: str


class StepThinkingEvent(_Event):
    type: Literal["STEP_THINKING"] = "STEP_THINKING"
    content: bool = True
    title: str | None = None
    thinking_status: Literal["start", "end"] | None = None


class StepStreamReasoningMessageEvent(_Event):
    type: Literal["STEP_STREAM_REASONING_MESSAGE"] = "STEP_STREAM_REASONING_MESSAGE"
    content: str
    group_id: str | None = None


class StepToolEvent(_Event):
    type: Literal["STEP_TOOL"] = "STEP_TOOL"
    tool_name: str
    tool_status: Literal["start", "end"]
    tool_call_id: str | None = None
    tool_description: str | None = None
    tool_type: str | None = None
    tool_tags: list[str] | None = None
    plugin_id: str | None = None
    plugin_name: str | None = None
    tool_input: str | None = None
    tool_content: str | None = None
    tool_artifact: Any = None
    tool_summary: Any = None


class StepStreamMessageEvent(_Event):
    type: Literal["STEP_STREAM_MESSAGE"] = "STEP_STREAM_MESSAGE"
    content: str
    group_id: str | None = None


class CardRegisterRequestEvent(_Event):
    type: Literal["CARD_REGISTER_REQUEST"] = "CARD_REGISTER_REQUEST"
    card_id: str
    card_data: dict[str, Any] | None = None
    card_description: str | None = None
    is_editable: bool = False


class FollowUpExpectedEvent(_Event):
    type: Literal["FOLLOW_UP_EXPECTED"] = "FOLLOW_UP_EXPECTED"


class StreamCardEvent(_Event):
    type: Literal["STREAM_CARD"] = "STREAM_CARD"
    card_id: str
    card_data: dict[str, Any] | None = None
    card_description: str | None = None
    is_editable: bool = False


class StreamMessageEvent(_Event):
    type: Literal["STREAM_MESSAGE"] = "STREAM_MESSAGE"
    content: str


class Reference(SphereModel):
    ref_num: int
    content: str
    resource_from: Literal["web", "knowledge_base", "external_resource", "tool"]
    execute_tool_id: str | None = None
    metadata: dict[str, Any] | None = None
    title: str | None = None
    url: str | None = None
    icon: str | None = None
    kb_id: str | None = None
    resource_id: str | None = None
    tool_name: str | None = None
    tool_description: str | None = None
    tool_input: str | None = None
    plugin_name: str | None = None


class ReferenceEvent(_Event):
    type: Literal["REFERENCE"] = "REFERENCE"
    references: list[Reference]


class AgentCustomMessageEvent(_Event):
    type: Literal["AGENT_CUSTOM_MESSAGE"] = "AGENT_CUSTOM_MESSAGE"
    custom_message_type: str
    content: str


class OutputEvent(_Event):
    type: Literal["OUTPUT"] = "OUTPUT"
    parts: list[OutputContent]


class IncapableEvent(_Event):
    type: Literal["INCAPABLE"] = "INCAPABLE"
    agent_name: str | None = None
    code: str | None = None
    message: str | None = None


class ErrorEvent(_Event):
    type: Literal["ERROR"] = "ERROR"
    error_code: str | None = None
    error_message: str | None = None
    error_detail: str | None = None


class EndEvent(_Event):
    type: Literal["END"] = "END"
    suggest_question: bool = False


WireEvent = (
    StartEvent
    | TaskEvent
    | InputRequiredFormEvent
    | ContainsPIIEvent
    | DisclaimerEvent
    | HeaderEvent
    | StepThinkingEvent
    | StepStreamReasoningMessageEvent
    | StepToolEvent
    | StepStreamMessageEvent
    | CardRegisterRequestEvent
    | FollowUpExpectedEvent
    | StreamCardEvent
    | StreamMessageEvent
    | ReferenceEvent
    | AgentCustomMessageEvent
    | OutputEvent
    | IncapableEvent
    | ErrorEvent
    | EndEvent
)
_event_adapter = TypeAdapter(Annotated[WireEvent, Field(discriminator="type")])


def parse_event(data: str) -> WireEvent:
    return _event_adapter.validate_json(data)
