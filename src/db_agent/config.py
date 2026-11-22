from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "postgres-database-agent"
    app_env: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+psycopg://db_agent:db_agent_password@localhost:5432/agent_demo"
    allowed_schemas: list[str] = Field(default_factory=lambda: ["public"])
    db_pool_size: int = 10
    db_max_overflow: int = 20
    statement_timeout_ms: int = 5000
    max_plan_cost: float = 0.0

    llm_api_key: str = "replace-me"
    llm_model: str = "replace-with-your-model-name"
    llm_base_url: str | None = None
    llm_temperature: float = 0.0

    max_rows: int = 100
    max_sql_retries: int = 2
    schema_top_k: int = 12
    schema_cache_ttl_seconds: int = 300
    return_sql: bool = True
    return_rows: bool = True

    @field_validator("allowed_schemas", mode="before")
    @classmethod
    def parse_schemas(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("llm_base_url", mode="before")
    @classmethod
    def empty_url_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
