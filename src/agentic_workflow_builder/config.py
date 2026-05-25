"""Application settings loaded from environment variables (or .env file).

pydantic-settings reads from the environment first, then falls back to .env.
All secrets stay out of code and logs.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://awb:awb@localhost:5432/awb"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: SecretStr = SecretStr("")
    run_token_budget: int = 50000


settings = Settings()
