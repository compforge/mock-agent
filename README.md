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

## Sphere protocol reference

See the [Sphere protocol reference](docs/sphere-protocol.md) for the request fields, SSE events, and runnable agent example. Executor posts a **bare `AgentRequest`** to the configured agent URL; the agent ID is already in `/v1/sphere/{agentid}/chat`. Mockagent also accepts the older `{ "bot_id": "echo", "agent_request": { ... } }` wrapper used by earlier sample clients.

```bash
curl -N http://127.0.0.1:8000/v1/sphere/echo/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "run_id": "run-1",
    "context_id": "conversation-1",
    "task_id": "task-1",
    "message": {"role": "user", "parts": [{"type": "text", "text": "original question"}]},
    "augmented_context": {"rewritten_query": "rewritten question"},
    "configuration": {"execution_mode": "sub_agent"}
  }'
```

The response is `text/event-stream`. Echo emits `STREAM_MESSAGE` with the original text and, when present, the exact `rewritten_query`; `/v1/sphere/demo/chat` also emits a final `OUTPUT`. `rewritten_query` is optional, and receipt logs distinguish a missing field, JSON `null`, an empty string, and a present value.

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

## CubeLoop agent

The `/v1/sphere/cubeloop/chat` route runs a new CubeLoop agent for each request, using the same `OPENAI_MODEL`, `OPENAI_API_KEY`, and optional `OPENAI_BASE_URL` settings as the LLM agent. It maps reply text to `STREAM_MESSAGE`, reasoning to `STEP_THINKING` and `STEP_STREAM_REASONING_MESSAGE`, tool execution to `STEP_TOOL`, and the final answer to `OUTPUT`. Tool events appear when tools are supplied to the CubeLoop agent; the built-in route does not register any tools. When `augmented_context.rewritten_query` is present, that value is the prompt, including an empty string; otherwise the prompt is the request message. Each request has independent conversation state.

```bash
uv run python examples/call_agent.py --agent-id cubeloop --message "hello mockagent"
```

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

Set `openai.baseUrl` and `openai.model` in chart values to inject `OPENAI_BASE_URL` and `OPENAI_MODEL` into the Pod. Keep personal overrides in an ignored `.local/values.yaml` and pass it with `-f .local/values.yaml` when running Helm.

Create a Kubernetes Secret containing the API key, then reference it in your values file:

```yaml
openai:
  apiKeySecret:
    name: mockagent-openai
    key: api-key
```

The chart injects `OPENAI_API_KEY` from that Secret. Keep the key value out of Helm values and the repository.
