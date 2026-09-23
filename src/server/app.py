from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from framework.default.echo import EchoAgentBuilder
from framework.default.llm import LLMAgentBuilder
from protocol.sphere import codec as sphere_codec
from server.api.chat import create_chat_router
from server.config import ServerConfig
from server.registry import AgentRegistry


def create_app(registry: AgentRegistry | None = None) -> FastAPI:
    llm_client = None
    if registry is None:
        config = ServerConfig()
        llm_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=60, write=10, pool=5),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        registry = AgentRegistry()
        registry.register_protocol("sphere", sphere_codec.Protocol())
        agent_config = config.to_agent_config()
        registry.register_agent(EchoAgentBuilder().build(agent_config))
        registry.register_agent(LLMAgentBuilder(llm_client).build(agent_config))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if llm_client is not None:
                await llm_client.aclose()

    app = FastAPI(title="Mockagent", lifespan=lifespan)
    app.include_router(create_chat_router(registry))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
