from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from framework.base import Agent
from protocol.base import AgentProtocol


def create_chat_router(agent: Agent, protocol: AgentProtocol) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/chats")
    async def chat(request: Request) -> StreamingResponse:
        try:
            input = protocol.decode_request(await request.json())
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=exc.errors(include_context=False)
            ) from exc

        return StreamingResponse(
            protocol.encode_stream(input, agent.run(input)),
            media_type="text/event-stream",
        )

    return router
