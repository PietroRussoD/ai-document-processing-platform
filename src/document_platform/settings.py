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
    max_document_pages: Annotated[int, Field(gt=0)] = 50
    max_extracted_text_characters: Annotated[int, Field(gt=0)] = 1_000_000
    minimum_embedded_text_characters: Annotated[int, Field(gt=0)] = 100
    tesseract_command: Annotated[str, Field(min_length=1)] = "tesseract"
    tesseract_language: Annotated[str, Field(min_length=1)] = "eng"
    tesseract_raster_dpi: Annotated[int, Field(ge=72, le=600)] = 200
    tesseract_page_timeout_seconds: Annotated[float, Field(gt=0, le=120)] = 30.0
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://document_platform:local-development-only@localhost:5432/"
        "document_platform"
    )
    database_pool_size: Annotated[int, Field(ge=1, le=20)] = 5
    database_max_overflow: Annotated[int, Field(ge=0, le=20)] = 5
    database_pool_timeout_seconds: Annotated[float, Field(gt=0, le=30)] = 5.0
    temporal_target_host: Annotated[str, Field(min_length=1, max_length=255)] = "localhost:7233"
    temporal_namespace: Annotated[str, Field(min_length=1, max_length=255)] = "default"
    temporal_task_queue: Annotated[str, Field(min_length=1, max_length=255)] = "document-processing"
    dispatcher_owner: Annotated[str, Field(min_length=1, max_length=64)] = "local-dispatcher"
    dispatcher_batch_size: Annotated[int, Field(ge=1, le=100)] = 10
    dispatcher_lease_seconds: Annotated[float, Field(gt=0, le=300)] = 30.0
    dispatcher_poll_seconds: Annotated[float, Field(gt=0, le=60)] = 2.0
