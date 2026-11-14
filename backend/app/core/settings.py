"""Environment settings (contract §4.1)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/multiverse.db"
    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = Path("./data")
    frontend_origin: str = "http://localhost:5173"
    job_mode: Literal["rq", "inprocess"] = "rq"
    max_histories: int = 5000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
