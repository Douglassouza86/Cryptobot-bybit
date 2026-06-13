"""Carregamento e validação das configurações YAML (pydantic)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator, model_validator


class DataConfig(BaseModel):
    """config/data.yaml — pares, timeframes e janela do histórico."""

    pairs: list[str]
    intervals: list[str] = ["60"]  # notação da API V5: "5", "15", "60"...
    start: datetime
    data_dir: Path = Path("data")

    @property
    def interval(self) -> str:
        """Timeframe principal (1h) — compatibilidade com a Fase 0/1."""
        return "60"

    @field_validator("start", mode="after")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def load_data_config(path: str | Path = Path("config/data.yaml")) -> DataConfig:
    with open(path, encoding="utf-8") as fh:
        return DataConfig(**yaml.safe_load(fh))


class WalkforwardWindows(BaseModel):
    """Split IS/OOS (T1.8, RF-005) — a otimização NUNCA enxerga o OOS."""

    is_start: datetime | None = None  # None = início dos dados
    is_end: datetime  # exclusivo
    oos_start: datetime  # inclusivo
    oos_end: datetime | None = None  # None = fim dos dados

    @field_validator("is_start", "is_end", "oos_start", "oos_end", mode="after")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _sem_sobreposicao(self) -> "WalkforwardWindows":
        if self.oos_start < self.is_end:
            raise ValueError("oos_start não pode ser anterior a is_end (vazaria IS no OOS)")
        return self


class BacktestConfig(BaseModel):
    """config/backtest.yaml — capital, custos e janelas (spec §2, congelado)."""

    initial_capital: float = 10_000.0
    taker_fee_pct: float = 0.055  # % por fill
    slippage_ticks: int = 2
    tick_size: dict[str, float]
    walkforward: WalkforwardWindows | None = None

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
