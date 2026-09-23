from framework.base import Agent
from protocol.base import AgentProtocol


class AgentRegistry:
    def __init__(self) -> None:
        self._protocols: dict[str, AgentProtocol] = {}
        self._agents: dict[tuple[str, str], Agent] = {}

    def register_protocol(self, name: str, protocol: AgentProtocol) -> None:
        if name in self._protocols:
            raise ValueError(f"Protocol {name!r} is already registered")
        self._protocols[name] = protocol

    def register_agent(self, agent: Agent) -> None:
        protocol_name = agent.protocol()
        agent_id = agent.ID()
        if protocol_name not in self._protocols:
            raise ValueError(
                f"Register protocol {protocol_name!r} before agent {agent_id!r}"
            )
        key = (protocol_name, agent_id)
        if key in self._agents:
            raise ValueError(
                f"Agent {agent_id!r} is already registered for {protocol_name!r}"
            )
        self._agents[key] = agent

    def get(
        self, protocol_name: str, agent_id: str
    ) -> tuple[AgentProtocol, Agent] | None:
        agent = self._agents.get((protocol_name, agent_id))
        if agent is None:
            return None
        return self._protocols[protocol_name], agent
