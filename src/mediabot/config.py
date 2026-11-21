"""Application settings loaded from the environment and .env (docs/PLAN.md §9.1)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    vault_dir: Path
    max_filesize_bytes: PositiveInt = 4 * 1024**3
    max_duration_seconds: PositiveInt = 10800

    @property
    def download_dir(self) -> Path:
        return self.vault_dir / "downloads"

    @property
    def work_dir(self) -> Path:
        return self.vault_dir / "work"


@cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
