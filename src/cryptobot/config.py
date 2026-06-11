"""Carregamento e validação das configurações YAML (pydantic)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class DataConfig(BaseModel):
    """config/data.yaml — pares, timeframe e janela do histórico."""

    pairs: list[str]
    interval: str = "60"
    start: datetime
    data_dir: Path = Path("data")

    @field_validator("start", mode="after")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def load_data_config(path: str | Path = Path("config/data.yaml")) -> DataConfig:
    with open(path, encoding="utf-8") as fh:
        return DataConfig(**yaml.safe_load(fh))
