"""Persistent audit storage (contract §3.2)."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, create_engine

from app.core.settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Audit(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str = "queued"
    config: dict[str, Any] = Field(sa_column=Column(JSON))
    config_hash: str = Field(index=True)
    verdict: str | None = None
    headline: str | None = None
    pbo: float | None = None
    dsr_prob: float | None = None
    survival_rate: float | None = None
    n_trials: int
    selected_variant: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class GeneratorModel(SQLModel, table=True):
    __tablename__ = "generator_model"
    id: str = Field(primary_key=True)
    type: str
    trained_on: dict[str, Any] = Field(sa_column=Column(JSON))
    weights_path: str
    realism_passed: bool | None = None
    created_at: datetime = Field(default_factory=utcnow)


class PriceCache(SQLModel, table=True):
    __tablename__ = "price_cache"
    symbol: str = Field(primary_key=True)
    start: str
    end: str
    parquet_path: str
    fetched_at: datetime = Field(default_factory=utcnow)


settings.data_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
