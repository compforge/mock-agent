import logging
from collections.abc import AsyncIterator

from agent_model import AgentEvent, AgentInput
from protocol.sphere.model import Failure, Input, TextDelta, WireEventOutput
from protocol.sphere.schema import (
    AgentChatRequest,
    AgentRequest,
    EndEvent,
    ErrorEvent,
    StartEvent,
    StreamMessageEvent,
    WireEvent,
)

# Uvicorn's configured logger makes receipt records visible in container logs.
logger = logging.getLogger("uvicorn.error")


def _sse(event: WireEvent) -> str:
    return f"data: {event.model_dump_json(exclude_none=True)}\n\n"


class Protocol:
    def decode_request(self, payload: object) -> Input:
        # Executor posts a bare AgentRequest. Older example clients wrap it in
        # AgentChatRequest; keep that format working while using the URL for routing.
        if isinstance(payload, dict) and "agent_request" in payload:
            wrapped = AgentChatRequest.model_validate(payload)
            request, bot_id = wrapped.agent_request, wrapped.bot_id
        else:
            request, bot_id = AgentRequest.model_validate(payload), None
        augmented_context = request.augmented_context
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
            bot_id,
            request.context_id,
            request.run_id,
            request.task_id,
            rewrite_status,
            augmented_context.contains_pii if augmented_context else False,
        )
        message = "\n".join(
            part.text
            for part in request.message.parts
            if part.type == "text" and part.text is not None
        )
        return Input(
            message=message,
            run_id=request.run_id,
            task_id=request.task_id,
            request=request,
            bot_id=bot_id,
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
                elif isinstance(event, WireEventOutput):
                    # Marker events are owned by the codec; all other documented
                    # event bodies can be emitted by a custom agent.
                    if isinstance(event.event, (StartEvent, EndEvent)):
                        raise TypeError("Agent must not emit START or END")
                    updates = {
                        key: value
                        for key, value in common.items()
                        if getattr(event.event, key) is None
                    }
                    yield _sse(event.event.model_copy(update=updates))
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
