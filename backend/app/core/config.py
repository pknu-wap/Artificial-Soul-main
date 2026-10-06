"""Typed settings, similar to application.yml and @ConfigurationProperties."""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client.models import Distance


class Settings(BaseSettings):
    # Resolve from this file so IDE working directories do not change .env lookup.
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # POSTGRES_* settings are consumed by Docker Compose.
        hide_input_in_errors=True,
    )

    database_url: PostgresDsn = Field(validation_alias="DATABASE_URL")
    qdrant_url: AnyHttpUrl = Field(validation_alias="QDRANT_URL")
    qdrant_collection_name: str = Field(
        default="artificial_soul_knowledge",
        min_length=1,
        validation_alias="QDRANT_COLLECTION_NAME",
    )
    # A model has not been selected. Health/lifespan do not require this value.
    qdrant_vector_size: int | None = Field(
        default=None, gt=0, validation_alias="QDRANT_VECTOR_SIZE"
    )
    qdrant_distance: Distance = Field(
        default=Distance.COSINE, validation_alias="QDRANT_DISTANCE"
    )
    health_check_timeout_seconds: float = Field(
        default=3.0, gt=0, validation_alias="HEALTH_CHECK_TIMEOUT_SECONDS"
    )

    @field_validator("database_url")
    @classmethod
    def require_asyncpg(cls, value: PostgresDsn) -> PostgresDsn:
        if value.scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg scheme")
        return value
