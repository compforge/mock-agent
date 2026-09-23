from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from framework.base import Agent
from framework.default.echo import EchoAgent
from framework.default.llm import LLMAgent
from protocol.base import AgentProtocol
from protocol.sphere import codec as sphere_codec
from server.api.chat import create_chat_router
from server.config import ServerConfig


def create_app(
    protocols: Mapping[str, AgentProtocol] | None = None,
    frameworks: Mapping[str, Sequence[Agent]] | None = None,
) -> FastAPI:
    llm_client = None
    if frameworks is None:
        config = ServerConfig()
        llm_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=60, write=10, pool=5),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        frameworks = {
            "default": (
                EchoAgent(),
                LLMAgent(
                    llm_client,
                    model=config.openai_model,
                    api_key=config.openai_api_key,
                    base_url=config.openai_base_url,
                ),
            )
        }

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if llm_client is not None:
                await llm_client.aclose()

    app = FastAPI(title="Mockagent", lifespan=lifespan)
    app.include_router(
        create_chat_router(
            protocols if protocols is not None else {"sphere": sphere_codec.Protocol()},
            frameworks,
        )
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
