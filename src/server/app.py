from collections.abc import Mapping, Sequence

from fastapi import FastAPI

from framework.base import Agent
from framework.default.echo import EchoAgent
from protocol.base import AgentProtocol
from protocol.sphere.codec import SphereProtocol
from server.api.chat import create_chat_router


def create_app(
    protocols: Mapping[str, AgentProtocol] | None = None,
    frameworks: Mapping[str, Sequence[Agent]] | None = None,
) -> FastAPI:
    app = FastAPI(title="Mockagent")
    app.include_router(
        create_chat_router(
            protocols if protocols is not None else {"sphere": SphereProtocol()},
            frameworks if frameworks is not None else {"default": (EchoAgent(),)},
        )
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
