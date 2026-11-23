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

    # Provider Configuration
    PAYMENT_PROVIDER: str = "internal"  # "internal" or "sepay"
    QR_PROVIDER: str = "internal"       # "internal" or "vietqr"

    # SePay Sandbox Provider Configuration
    SEPAY_MERCHANT_ID: Optional[str] = None
    SEPAY_SECRET_KEY: Optional[str] = None
    SEPAY_BASE_URL: str = "https://pgapi-sandbox.sepay.vn"
    SEPAY_CHECKOUT_URL: str = "https://pay-sandbox.sepay.vn/v1/checkout/init"
    SEPAY_FALLBACK_TO_SIMULATION: bool = True
    SEPAY_TIMEOUT_SECONDS: float = 5.0

    # VietQR Configuration
    VIETQR_DEFAULT_BANK_BIN: str = "970436"  # Vietcombank BIN
    VIETQR_DEFAULT_TEMPLATE: str = "compact2"

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

