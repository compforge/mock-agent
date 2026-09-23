from framework.base import AgentConfig
from server.config import DEFAULT_OPENAI_BASE_URL, ServerConfig


def test_server_config_reads_openai_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example/v1")

    config = ServerConfig()

    assert config.openai_model == "test-model"
    assert config.openai_api_key == "test-key"
    assert config.openai_base_url == "https://llm.example/v1"
    assert config.to_agent_config() == AgentConfig(
        model="test-model", api_key="test-key", base_url="https://llm.example/v1"
    )


def test_empty_openai_base_url_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "")

    assert ServerConfig().openai_base_url == DEFAULT_OPENAI_BASE_URL
