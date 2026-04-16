from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "drawagent-backend"
    version: str = "0.1.0"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://127.0.0.1:5173"
    log_level: str = "INFO"
    temp_dir: str = "./tmp"
    session_ttl_seconds: int = 1800
    session_cleanup_interval_seconds: int = 300
    max_session_files: int = 10
    max_session_file_size_mb: int = 25
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 2
    image_api_key: str = ""
    image_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
