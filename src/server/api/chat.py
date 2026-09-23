from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from server.registry import AgentRegistry


def create_chat_router(registry: AgentRegistry) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/{protocol}/{agentid}/chat")
    async def chat(request: Request, protocol: str, agentid: str) -> StreamingResponse:
        route = registry.get(protocol, agentid)
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
