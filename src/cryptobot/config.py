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


class BacktestConfig(BaseModel):
    """config/backtest.yaml — capital, custos e janelas (spec §2, congelado)."""

    initial_capital: float = 10_000.0
    taker_fee_pct: float = 0.055  # % por fill
    slippage_ticks: int = 2
    tick_size: dict[str, float]
    walkforward: dict | None = None  # modelado em T1.8

    @property
    def taker_fee(self) -> float:
        """Taxa por fill em fração (0.055% -> 0.00055)."""
        return self.taker_fee_pct / 100.0

    def slippage(self, symbol: str) -> float:
        """Slippage em unidades de preço para o símbolo."""
        return self.slippage_ticks * self.tick_size[symbol]


def load_backtest_config(path: str | Path = Path("config/backtest.yaml")) -> BacktestConfig:
    with open(path, encoding="utf-8") as fh:
        return BacktestConfig(**yaml.safe_load(fh))
