from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "Bid Platform API"
    environment: str = "development"
    database_url: str = "sqlite:///./bid_platform.sqlite3"
    redis_url: str = ""
    file_storage_path: Path = Path("./data/files")
    max_upload_bytes: int = 50 * 1024 * 1024
    max_docx_uncompressed_bytes: int = 250 * 1024 * 1024
    session_cookie_name: str = "bid_session"
    session_secret: str = "development-session-secret"
    session_secure: bool = False
    session_ttl_hours: int = 12
    admin_username: str = "admin"
    admin_password: str = "ChangeMe123!"
    tasks_sync: bool | None = None
    ai_enabled: bool = False
    ai_base_url: str = ""
    ai_api_key: str = Field(default="", repr=False)
    ai_model: str = ""
    ai_timeout_seconds: float = 90
    ai_prompt_version: str = "v1"
    libreoffice_binary: str = "libreoffice"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def synchronous_tasks(self) -> bool:
        if self.tasks_sync is not None:
            return self.tasks_sync
        return not self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
