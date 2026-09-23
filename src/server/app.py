from fastapi import FastAPI

from framework.base import Agent
from framework.echo import EchoAgent
from protocol.agentsphere.codec import AgentSphereProtocol
from protocol.base import AgentProtocol
from server.api.chat import create_chat_router


def create_app(
    agent: Agent | None = None, protocol: AgentProtocol | None = None
) -> FastAPI:
    app = FastAPI(title="Mockagent")
    app.include_router(
        create_chat_router(agent or EchoAgent(), protocol or AgentSphereProtocol())
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
