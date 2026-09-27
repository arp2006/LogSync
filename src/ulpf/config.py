from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://ulpf_user:ulpf_password@localhost:5432/ulpf_db",
        description="SQLAlchemy database connection string",
    )
    raw_data_dir: Path = Field(
        default=Path("data/raw"),
        description="Root directory for immutable raw evidence files",
    )
    max_upload_size_bytes: int = Field(
        default=104_857_600,  # 100 MB
        description="Maximum allowed upload payload in bytes",
    )
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    ocsf_version: str = Field(default="1.1.0")


settings = Settings()
