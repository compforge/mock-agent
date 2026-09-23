# Mockagent

Mockagent is a small Python web server for emulating a downstream agent. Use it to check that your application sends the expected input and handles streamed responses without running a full agent stack.

An API handler pairs an agent implementation with a protocol adapter. The agent receives an `AgentInput` and yields `AgentEvent` values; the adapter translates between those values and the HTTP stream. The included Echo agent returns the message it receives. The LLM agent sends one streaming Chat Completions request to an OpenAI-compatible endpoint and forwards text chunks as agent events.

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

## LLM agent

Set a model and API key before starting the server:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model"
uv run uvicorn server.app:app --reload
```

In another terminal, call `/v1/sphere/default/llm/chat`:

```bash
uv run python examples/call_agent.py --agent-id llm --message "hello mockagent"
```

To use another OpenAI-compatible provider, set `OPENAI_BASE_URL` to its API base URL before starting the server. The LLM agent streams text chunks back to the caller. A missing model or API key produces an SSE `ERROR` event.

## Extend Mockagent

Implement `Agent.run(input: AgentInput) -> AsyncIterator[AgentEvent]` to add an agent behavior. Each protocol defines its own input and event subclasses. Register agents with `create_app(frameworks={"default": (YourAgent(),)})` and protocols with `create_app(protocols={"your_protocol": YourProtocol()})`.

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
