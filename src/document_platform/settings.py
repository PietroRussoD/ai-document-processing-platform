"""Typed process configuration."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from document_platform.domain.processing import ProcessingStage

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
    parser_kubernetes_endpoint: str | None = None
    parser_kubernetes_namespace: str | None = None
    parser_kubernetes_ca_file: Path | None = None
    parser_kubernetes_token_file: Path | None = None
    parser_job_image: str | None = None
    tesseract_language: Annotated[str, Field(min_length=1)] = "eng"
    tesseract_raster_dpi: Annotated[int, Field(ge=72, le=600)] = 200
    tesseract_max_page_pixels: Annotated[int, Field(gt=0)] = 20_000_000
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
    ollama_enabled: bool = False
    ollama_base_url: Annotated[str, Field(min_length=1)] = "http://localhost:11434"
    ollama_model_reference: Annotated[str, Field(min_length=1, max_length=200)] = "qwen3:8b"
    ollama_model_digest: str | None = None
    ollama_timeout_seconds: Annotated[float, Field(gt=0, le=120)] = 60.0
    ollama_max_concurrent_requests: Annotated[int, Field(ge=1, le=8)] = 1
    dispatcher_owner: Annotated[str, Field(min_length=1, max_length=64)] = "local-dispatcher"
    dispatcher_batch_size: Annotated[int, Field(ge=1, le=100)] = 10
    dispatcher_lease_seconds: Annotated[float, Field(gt=0, le=300)] = 30.0
    dispatcher_poll_seconds: Annotated[float, Field(gt=0, le=60)] = 2.0
    review_operator_token: SecretStr | None = None
    review_operator_id: Annotated[str, Field(min_length=1, max_length=200)] = "local-reviewer"
    fault_injection_stage: ProcessingStage | None = None
    fault_injection_crash_after_ocr_persistence: bool = False

    @model_validator(mode="after")
    def validate_fault_injection(self) -> Self:
        if (
            self.fault_injection_stage is None
            and not self.fault_injection_crash_after_ocr_persistence
        ):
            return self
        if self.environment != "local":
            raise ValueError("fault injection is supported only in the local environment")
        if (
            self.fault_injection_stage is not None
            and self.fault_injection_stage is not ProcessingStage.EMBEDDED_TEXT_EXTRACTION
        ):
            raise ValueError("fault_injection_stage supports only EMBEDDED_TEXT_EXTRACTION")
        return self

    @field_validator("review_operator_token")
    @classmethod
    def validate_review_operator_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("review_operator_token must contain at least 32 characters")
        return value

    @field_validator("review_operator_id")
    @classmethod
    def validate_review_operator_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("review_operator_id must not be blank")
        return value
