import argparse
import asyncio

import httpx

from client.sphere import stream_chat
from protocol.sphere.schema import (
    AgentAugmentedContext,
    AgentMessage,
    AgentRequest,
    MessagePart,
)


async def main(url: str, message: str, rewritten_query: str | None) -> None:
    request = AgentRequest(
        message=AgentMessage(
            role="user", parts=[MessagePart(type="text", text=message)]
        ),
        augmented_context=(
            AgentAugmentedContext(rewritten_query=rewritten_query)
            if rewritten_query is not None
            else None
        ),
    )
    async with httpx.AsyncClient(timeout=90) as client:
        async for event in stream_chat(client, url, request):
            print(event.model_dump_json(exclude_none=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--agent-id", default="echo")
    parser.add_argument("--message", default="hello mockagent")
    parser.add_argument("--rewritten-query")
    args = parser.parse_args()
    url = args.url or f"http://127.0.0.1:8000/v1/sphere/{args.agent_id}/chat"
    asyncio.run(main(url, args.message, args.rewritten_query))
