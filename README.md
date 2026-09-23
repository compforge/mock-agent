# Mockagent

Mockagent 是一个可运行的 HTTP mock agent，用来检查调用方能否向下游 agent 发出请求，以及能否正确消费它的 SSE 回复。它把 agent 的输入/事件与对外协议分开：同一个 agent 实现可以由不同协议对外提供服务。

当前内置一个 Echo agent 和 AgentSphere 基础请求/SSE 协议。Echo 会把收到的消息作为 `STREAM_MESSAGE` 发回；服务也会发出 `START` 和 `END`。后续可以在 `framework` 增加 agent 实现，在 `protocol` 增加协议适配器。

## 快速开始

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run uvicorn server.app:app --reload
```

另开终端发送一个请求：

```bash
uv run python examples/call_agent.py --message 'hello mockagent'
```

也可以直接调用 `POST /api/v1/chats`：

```bash
curl -N http://127.0.0.1:8000/api/v1/chats \
  -H 'Content-Type: application/json' \
  -d '{"bot_id":"echo","agent_request":{"message":{"role":"user","parts":[{"type":"text","text":"hello mockagent"}]}}}'
```

服务返回 `text/event-stream`，每个 `data:` 块是一个带 `type` 的 JSON 事件。客户端示例和可复用的流式调用函数位于 `examples/call_agent.py` 与 `src/client/agentsphere.py`。

