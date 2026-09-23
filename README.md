# Mockagent

Mockagent is a small Python web server for emulating a downstream agent. Use it to check that your application sends the expected input and handles streamed responses without running a full agent stack.

Register protocol adapters and agents at startup. An agent receives an `AgentInput` and yields `AgentEvent` values; its protocol adapter translates between those values and the HTTP stream. The included Echo agent returns the message it receives. The LLM agent sends one streaming Chat Completions request to an OpenAI-compatible endpoint and forwards text chunks as agent events.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn server.app:app --reload
```

In another terminal, use the sample client to send a message:

```bash
uv run python examples/call_agent.py --message "hello mockagent"
```

The client prints the streamed events, including Echo's response to the message.

## Check received requests

Each valid Sphere request produces a `sphere request received` log line with its bot, context, run, and task IDs. `rewritten_query_status` is `missing`, `null`, `empty`, or `present`, so you can check whether a caller sent the field without logging the user's message or rewritten text. Match the IDs with the calling application; use Echo's streamed response when you need to compare the exact rewritten query.

## LLM agent

Set a model and API key before starting the server:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model"
uv run uvicorn server.app:app --reload
```

In another terminal, call `/v1/sphere/llm/chat`:

```bash
uv run python examples/call_agent.py --agent-id llm --message "hello mockagent"
```

To use another OpenAI-compatible provider, set `OPENAI_BASE_URL` to its API base URL before starting the server. The LLM agent streams text chunks back to the caller. A missing model or API key produces an SSE `ERROR` event.

## Extend Mockagent

Implement `Agent.ID()`, `Agent.protocol()` and `Agent.run(input: AgentInput) -> AsyncIterator[AgentEvent]` to add an agent behavior. Pair it with an `AgentBuilder` whose `build(config: AgentConfig)` creates the agent. `protocol()` returns the name of the supported protocol. Each protocol defines its own input and event subclasses. Register its adapter before building and registering its agents:

```python
from server.app import create_app
from server.config import ServerConfig
from server.registry import AgentRegistry

registry = AgentRegistry()
registry.register_protocol("your_protocol", YourProtocol())
config = ServerConfig().to_agent_config()
registry.register_agent(YourAgentBuilder().build(config))
app = create_app(registry)
```

Replace `YourProtocol` and `YourAgentBuilder` with your implementations.

## Deploy

Build the image from the repository root, then publish it to a registry you can access from your cluster:

```bash
docker build -f deploy/docker/Dockerfile -t registry.example.com/mockagent:0.1.0 .
docker push registry.example.com/mockagent:0.1.0
```

Install the Helm chart with that image:

```bash
helm upgrade --install mockagent deploy/k8s/helm/mockagent \
  --set image.repository=registry.example.com/mockagent \
  --set image.tag=0.1.0
```

Replace the example registry and tag with your own. The chart creates a Deployment and a ClusterIP Service; its readiness and liveness probes use `/health`.

Set `openai.baseUrl` in the chart values, or pass `--set-string openai.baseUrl=https://provider.example.com/v1` to Helm, to inject `OPENAI_BASE_URL` into the Pod. The LLM agent also needs `OPENAI_MODEL` and `OPENAI_API_KEY` in its environment.
