from collections.abc import Mapping, Sequence

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from framework.base import Agent
from protocol.base import AgentProtocol


def create_chat_router(
    protocols: Mapping[str, AgentProtocol],
    frameworks: Mapping[str, Sequence[Agent]],
) -> APIRouter:
    router = APIRouter()
    agents_by_framework = {
        framework: {agent.ID(): agent for agent in agents}
        for framework, agents in frameworks.items()
    }

    @router.post("/v1/{protocol}/{framework}/{agentid}/chat")
    async def chat(
        request: Request, protocol: str, framework: str, agentid: str
    ) -> StreamingResponse:
        selected_protocol = protocols.get(protocol)
        selected_agent = agents_by_framework.get(framework, {}).get(agentid)
        if selected_protocol is None or selected_agent is None:
            raise HTTPException(status_code=404, detail="Unknown agent route")

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
