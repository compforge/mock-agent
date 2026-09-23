from pydantic_settings import BaseSettings, SettingsConfigDict

from framework.base import AgentConfig

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class ServerConfig(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True)

    openai_model: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL

    def to_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model=self.openai_model,
            api_key=self.openai_api_key,
            base_url=self.openai_base_url,
        )
