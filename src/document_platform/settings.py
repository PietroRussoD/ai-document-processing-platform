"""Typed process configuration."""

from typing import Literal

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
