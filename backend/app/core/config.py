from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Security
    SECRET_KEY: str = Field(default="leakcheck-development-secret-key-32-chars-minimum")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Database
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_HOST: str = Field(default="127.0.0.1")
    POSTGRES_PORT: int = Field(default=5433)
    POSTGRES_DB: str = Field(default="leakcheck")
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres@127.0.0.1:5433/leakcheck"
    )

    # CORS
    ALLOWED_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # Reconciliation Defaults
    DEFAULT_AS_OF_DATE: str = Field(default="2026-11-01")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
