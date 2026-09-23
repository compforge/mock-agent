import os
from dataclasses import dataclass

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class LLMConfig:
    model: str | None
    api_key: str | None
    base_url: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            model=os.environ.get("OPENAI_MODEL"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL,
        )
