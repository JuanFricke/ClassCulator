from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "dev"
    APP_PORT: int = 8000
    SECRET_KEY: str = "dev-secret-change-me"

    EMPRESA_NOME: str = "Administração"
    EMPRESA_EMAIL: str = "empresa@classculator.local"
    EMPRESA_SENHA: str = "trocar-esta-senha"

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://classculator:classculator@db:5432/classculator"
    )
    SYNC_DATABASE_URL: str = Field(
        default="postgresql+psycopg://classculator:classculator@db:5432/classculator"
    )

    SOLVER_DEFAULT: str = "cpsat"
    SOLVER_TIMEOUT_S: int = 30
    HILL_CLIMBING_ITERATIONS: int = 800

    DIAS: int = 5
    SLOTS: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
