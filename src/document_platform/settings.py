"""Typed process configuration."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

type Environment = Literal["local", "test", "production"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DOCUMENT_PLATFORM_",
        extra="ignore",
    )

    environment: Environment = "local"
    log_level: LogLevel = "INFO"
    storage_root: Path = Path("data")
    max_document_bytes: Annotated[int, Field(gt=0)] = 20 * 1024 * 1024
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://document_platform:local-development-only@localhost:5432/"
        "document_platform"
    )
    database_pool_size: Annotated[int, Field(ge=1, le=20)] = 5
    database_max_overflow: Annotated[int, Field(ge=0, le=20)] = 5
    database_pool_timeout_seconds: Annotated[float, Field(gt=0, le=30)] = 5.0
