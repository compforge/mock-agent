"""Run CubeLoop behind the existing Sphere mock-agent route."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress

from cubeloop import Agent as RuntimeAgent
from cubeloop import AgentTool, BoundModel, TextContent
from cubeloop.agent.types import (
    AgentEndEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
)
from cubeloop.providers.openai import OpenAIProvider

from agent_model import AgentEvent, AgentInput
from framework.base import AgentConfig
from protocol.sphere.model import Failure, Input, TextDelta, WireEventOutput
from protocol.sphere.schema import (
    OutputEvent,
    StepStreamReasoningMessageEvent,
    StepThinkingEvent,
    StepToolEvent,
    TextPart,
)

logger = logging.getLogger(__name__)


class CubeLoopAgentBuilder:
    def build(self, config: AgentConfig) -> "CubeLoopAgent":
        if not config.model or not config.api_key:
            return CubeLoopAgent(None)
        provider = OpenAIProvider(
            provider_id="openai",
            api_key=config.api_key,
            base_url=config.base_url,
        )
        return CubeLoopAgent(provider.model(config.model), provider=provider)


class CubeLoopAgent:
    def __init__(
        self,
        model: BoundModel | None,
        *,
        provider: OpenAIProvider | None = None,
        tools: list[AgentTool] | None = None,
    ) -> None:
        self._model = model
        self._provider = provider
        self._tools = tools

    def ID(self) -> str:
        return "cubeloop"

    def protocol(self) -> str:
        return "sphere"

    async def aclose(self) -> None:
        if self._provider is not None:
            # CubeLoop 0.15 does not expose provider.close(); release its SDK client.
            await self._provider._client.close()

    async def run(self, input: AgentInput) -> AsyncIterator[AgentEvent]:
        if not isinstance(input, Input):
            raise TypeError("CubeLoopAgent requires a Sphere request")
        if self._model is None:
            yield Failure(
                code="CUBELOOP_NOT_CONFIGURED",
                message="Set OPENAI_API_KEY and OPENAI_MODEL",
            )
            return

        # A fresh runtime keeps independent Sphere requests from sharing chat history.
        agent = RuntimeAgent(model=self._model, tools=self._tools)
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        final_text: str | None = None
        failed = False

        def on_event(event, signal=None) -> None:
            nonlocal final_text, failed
            if isinstance(event, MessageUpdateEvent):
                stream_event = event.stream_event
                if stream_event.type == "text_delta" and stream_event.delta:
                    queue.put_nowait(TextDelta(content=stream_event.delta))
                elif stream_event.type in ("thinking_start", "thinking_end"):
                    queue.put_nowait(
                        WireEventOutput(
                            StepThinkingEvent(
                                thinking_status=(
                                    "start"
                                    if stream_event.type == "thinking_start"
                                    else "end"
                                )
                            )
                        )
                    )
                elif stream_event.type == "thinking_delta" and stream_event.delta:
                    queue.put_nowait(
                        WireEventOutput(
                            StepStreamReasoningMessageEvent(content=stream_event.delta)
                        )
                    )
            elif isinstance(event, ToolExecutionStartEvent):
                queue.put_nowait(
                    WireEventOutput(
                        StepToolEvent(
                            tool_name=event.tool_name,
                            tool_status="start",
                            tool_call_id=event.tool_call_id,
                            tool_input=json.dumps(event.args, ensure_ascii=False),
                        )
                    )
                )
            elif isinstance(event, ToolExecutionEndEvent):
                result = event.model_dump(mode="json")["result"]
                queue.put_nowait(
                    WireEventOutput(
                        StepToolEvent(
                            tool_name=event.tool_name,
                            tool_status="end",
                            tool_call_id=event.tool_call_id,
                            tool_content=(
                                json.dumps(result, ensure_ascii=False)
                                if result is not None
                                else None
                            ),
                        )
                    )
                )
            elif isinstance(event, TurnEndEvent):
                if event.message.stop_reason in ("error", "aborted"):
                    failed = True
                    logger.warning(
                        "CubeLoop turn failed run_id=%r reason=%s",
                        input.run_id,
                        event.message.stop_reason,
                    )
                    queue.put_nowait(
                        Failure(
                            code="CUBELOOP_UPSTREAM_ERROR",
                            message="CubeLoop model request failed",
                        )
                    )
                else:
                    final_text = "".join(
                        part.text
                        for part in event.message.content
                        if isinstance(part, TextContent)
                    )
            elif (
                isinstance(event, AgentEndEvent)
                and not failed
                and final_text is not None
            ):
                # OUTPUT is the durable result consumed by downstream agents.
                queue.put_nowait(
                    WireEventOutput(OutputEvent(parts=[TextPart(text=final_text)]))
                )

        agent.subscribe(on_event)

        async def execute() -> None:
            try:
                query = (
                    input.rewritten_query
                    if input.rewritten_query is not None
                    else input.message
                )
                await agent.prompt(query, run_id=input.run_id)
            except Exception:
                logger.exception("CubeLoop run failed", extra={"run_id": input.run_id})
                queue.put_nowait(
                    Failure(
                        code="CUBELOOP_UPSTREAM_ERROR",
                        message="CubeLoop model request failed",
                    )
                )
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(execute())
        try:
            while (event := await queue.get()) is not None:
                yield event
        finally:
            if not task.done():
                agent.abort()
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task
