import logging
from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentFailure, AgentInput, TextDelta
from protocol.sphere.schema import (
    AgentChatRequest,
    EndEvent,
    ErrorEvent,
    StartEvent,
    StreamMessageEvent,
)

logger = logging.getLogger(__name__)


def _sse(event: StartEvent | StreamMessageEvent | ErrorEvent | EndEvent) -> str:
    return f"data: {event.model_dump_json(exclude_none=True)}\n\n"


class SphereProtocol:
    def decode_request(self, payload: object) -> AgentInput:
        request = AgentChatRequest.model_validate(payload)
        message = "\n".join(
            part.text
            for part in request.agent_request.message.parts
            if part.type == "text" and part.text is not None
        )
        augmented_context = request.agent_request.augmented_context
        return AgentInput(
            message=message,
            bot_id=request.bot_id,
            run_id=request.agent_request.run_id,
            task_id=request.agent_request.task_id,
            rewritten_query=(
                augmented_context.rewritten_query if augmented_context else None
            ),
        )

    async def encode_stream(
        self, input: AgentInput, events: AsyncIterator[AgentEvent]
    ) -> AsyncIterator[str]:
        common = {"run_id": input.run_id, "task_id": input.task_id}
        yield _sse(StartEvent(**common))
        try:
            async for event in events:
                if isinstance(event, TextDelta):
                    yield _sse(StreamMessageEvent(content=event.content, **common))
                elif isinstance(event, AgentFailure):
                    yield _sse(
                        ErrorEvent(
                            error_code=event.code,
                            error_message=event.message,
                            **common,
                        )
                    )
                    break
        except Exception:
            logger.exception(
                "mock agent execution failed", extra={"run_id": input.run_id}
            )
            yield _sse(
                ErrorEvent(
                    error_code="MOCK_AGENT_ERROR",
                    error_message="Mock agent execution failed",
                    **common,
                )
            )
        yield _sse(EndEvent(**common))
