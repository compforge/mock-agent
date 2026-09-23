# AGENTS.md

## 项目定位与边界

Mockagent 是用于模拟下游 agent HTTP/SSE 行为的开源服务。协议适配器处理外部请求和事件格式，将它们映射到项目内的输入和事件模型；API 层组合协议与 agent 实现。运行时不依赖私有 Agent SDK。

## 代码地图与核心模块

```text
src/
  agent_model.py          # 协议无关的 AgentInput 与 AgentEvent
  server/
    app.py                # 创建应用并绑定默认协议与 agent
    config.py             # 服务配置与环境变量入口
    api/                  # HTTP handler；只负责组合与返回响应
  protocol/
    base.py               # 协议适配接口
    sphere/               # Sphere 输入/事件子类、请求模型及 SSE 编解码
  framework/
    base.py               # Agent 接口
    default/              # 不依赖外部 agent framework 的内置实现
  client/                 # HTTP 调用封装，复用协议模型
examples/                 # 可运行的客户端示例
tests/                    # API 与客户端行为验证
```

## 关键约定

- `AgentInput` 与 `AgentEvent` 是全局基类，只放不同协议都能复用的字段和事件语义。每个 `protocol/<name>/` 定义自己的输入和事件子类；协议字段、请求校验和 SSE 编码由该目录负责，不让 handler 或 agent 实现解析协议载荷。
- 一个协议放在 `protocol/` 的一个目录。`framework/default/` 收纳不依赖外部 agent framework 的实现；接入其他 framework 时在 `framework/` 下单独建目录，公共接口保留在 `framework/base.py`。
- `Agent.ID()` 返回实现的公开 ID；`Agent.run(input)` 的调用结果是 `AsyncIterator[AgentEvent]`。具体实现使用带 `yield` 的 `async def`，接口声明返回异步迭代器，不声明为需要先 `await` 的协程。
- `/v1/{protocol}/{framework}/{agentid}/chat` 通过显式注册选择协议和 agent。`server/api` 只做选择、组合与 HTTP 边界处理；路径上的 `agentid` 与协议载荷中的身份字段各有职责。客户端通过 `protocol` 中的模型和事件解析函数复用协议契约。

## 验证与参考

- 修改 Python 代码后运行 `make fix`、`make lint` 和 `make test`；改动包布局时再运行 `uv build`。
- 使用与启动方式见 [README.md](README.md)，现有 API 与客户端场景见 `tests/`。
