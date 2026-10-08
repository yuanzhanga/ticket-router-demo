from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ticket Router Demo"
    database_path: str = "./tickets.db"
    frontend_origin: str = "http://localhost:5173"

    jev_api_url: str = ""
    jev_api_key: str = ""
    jev_model: str = "jev"
    jev_timeout_seconds: float = 30

    llm_enabled: bool = False
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 45

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

