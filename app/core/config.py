"""Application configuration settings."""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Fintech Sandbox API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Database connection
    DATABASE_URL: str = "sqlite:///./fintech_sandbox.db"

    # Security & Tokens
    SECRET_KEY: str = "demo_dev_secret_key_change_in_production_32bytes_min!"
    SESSION_TOKEN_EXPIRE_HOURS: int = 24

    # Demo Session settings
    DEFAULT_SEED_SCENARIO: str = "scenario_a"
    ALLOW_DEMO_RESET: bool = True

    # Host & Port
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
