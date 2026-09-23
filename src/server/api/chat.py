from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from framework.base import Agent
from protocol.base import AgentProtocol


@dataclass(frozen=True)
class ChatBinding:
    protocol: AgentProtocol
    agents: Sequence[Agent]


def create_chat_router(
    bindings: Mapping[str, ChatBinding],
) -> APIRouter:
    router = APIRouter()
    routes = {
        (protocol_name, agent.ID()): (binding.protocol, agent)
        for protocol_name, binding in bindings.items()
        for agent in binding.agents
    }

    @router.post("/v1/{protocol}/{agentid}/chat")
    async def chat(request: Request, protocol: str, agentid: str) -> StreamingResponse:
        route = routes.get((protocol, agentid))
        if route is None:
            raise HTTPException(status_code=404, detail="Unknown agent route")
        selected_protocol, selected_agent = route

        try:
            input = selected_protocol.decode_request(await request.json())
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=exc.errors(include_context=False)
            ) from exc

        return StreamingResponse(
            selected_protocol.encode_stream(input, selected_agent.run(input)),
            media_type="text/event-stream",
        )

    return router
