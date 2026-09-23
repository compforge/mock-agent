import logging
from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentInput
from protocol.sphere.model import Failure, Input, TextDelta
from protocol.sphere.schema import (
    AgentChatRequest,
    EndEvent,
    ErrorEvent,
    StartEvent,
    StreamMessageEvent,
)

# Uvicorn's configured logger makes receipt records visible in container logs.
logger = logging.getLogger("uvicorn.error")


def _sse(event: StartEvent | StreamMessageEvent | ErrorEvent | EndEvent) -> str:
    return f"data: {event.model_dump_json(exclude_none=True)}\n\n"


class Protocol:
    def decode_request(self, payload: object) -> Input:
        request = AgentChatRequest.model_validate(payload)
        augmented_context = request.agent_request.augmented_context
        rewrite_status = "missing"
        if (
            augmented_context is not None
            and "rewritten_query" in augmented_context.model_fields_set
        ):
            if augmented_context.rewritten_query is None:
                rewrite_status = "null"
            elif augmented_context.rewritten_query == "":
                rewrite_status = "empty"
            else:
                rewrite_status = "present"
        # Request IDs are caller-controlled; %r escapes log-breaking control characters.
        logger.info(
            "sphere request received bot_id=%r context_id=%r run_id=%r task_id=%r "
            "rewritten_query_status=%s contains_pii=%s",
            request.bot_id,
            request.agent_request.context_id,
            request.agent_request.run_id,
            request.agent_request.task_id,
            rewrite_status,
            augmented_context.contains_pii if augmented_context else False,
        )
        message = "\n".join(
            part.text
            for part in request.agent_request.message.parts
            if part.type == "text" and part.text is not None
        )
        return Input(
            message=message,
            run_id=request.agent_request.run_id,
            task_id=request.agent_request.task_id,
            bot_id=request.bot_id,
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
                elif isinstance(event, Failure):
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
