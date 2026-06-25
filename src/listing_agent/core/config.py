from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SQLITE_ASYNC_PREFIX = "sqlite+aiosqlite:///"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Amazon Listing Agent"
    app_env: str = "local"
    app_debug: bool = False
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./listing_agent.db"
    app_data_dir: str = "./data"

    llm_provider: str = "openai"
    llm_model: str | None = None
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_base_url: str | None = None
    llm_thinking_config: str = "disabled"

    # Backward-compatible aliases for existing local .env files.
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-4o-mini"


    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model or self.openai_model

    @property
    def resolved_llm_api_key(self) -> str | None:
        return self.llm_api_key or self.openai_api_key

    @property
    def is_llm_configured(self) -> bool:
        return bool(self.resolved_llm_api_key)

    @property
    def is_openai_configured(self) -> bool:
        return self.is_llm_configured

    @property
    def resolved_database_url(self) -> str:
        """Resolve relative SQLite paths from the project root, not the process cwd."""
        if not self.database_url.startswith(SQLITE_ASYNC_PREFIX):
            return self.database_url

        database_path = self.database_url.removeprefix(SQLITE_ASYNC_PREFIX)
        if database_path in {":memory:", ""}:
            return self.database_url

        path = Path(database_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return f"{SQLITE_ASYNC_PREFIX}{path.resolve().as_posix()}"

    @property
    def resolved_app_data_dir(self) -> Path:
        """Resolve generated backend data storage from the project root."""
        path = Path(self.app_data_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
