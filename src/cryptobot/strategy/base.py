"""Blocos compartilhados das estratégias e modelo de parâmetros (RF-006).

Tudo aqui é função pura sobre candles 1h (índice UTC, candles fechados):
o valor em `t` depende apenas de dados `<= t`. Ver docs/strategy-v2-spec.md §4.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, Field, model_validator

from cryptobot.indicators import ema, sma

DEFAULT_PARAMS_PATH = Path("config/strategies/ema_rsi_v2.yaml")

# Contrato de saída das funções de sinal (consumido pelo motor em T1.4):
# long_entry/short_entry no candle do SINAL (execução na abertura do seguinte),
# atr do candle do sinal (congela distâncias de stop/alvo/trailing e sizing).
SIGNAL_COLUMNS = ["long_entry", "short_entry", "atr"]


class EmaRsiV2Params(BaseModel):
    """Parâmetros da família v2 (defaults = inputs dos .pine, spec §6)."""

    # Tendência local (1h)
    ema_fast: int = Field(50, ge=1)
    ema_slow: int = Field(200, ge=1)
    # Gatilho
    rsi_len: int = Field(14, ge=2)
    rsi_long_lvl: float = Field(45.0, ge=0.0, le=100.0)
    rsi_short_lvl: float = Field(55.0, ge=0.0, le=100.0)
    # Filtro multi-timeframe
    use_daily: bool = True
    use_weekly: bool = False
    htf_ema_len: int = Field(21, ge=1)
    htf_lag: int = Field(1, ge=1, le=2)
    # Filtro de volume
    use_vol_filter: bool = True
    vol_ma_len: int = Field(20, ge=1)
    vol_mult: float = Field(1.2, gt=0.0)
    # Risco / saídas
    atr_len: int = Field(14, ge=1)
    stop_mult: float = Field(1.5, gt=0.0)
    tp_mult: float = Field(2.5, gt=0.0)
    use_trailing: bool = False
    trail_trigger: float = Field(1.5, gt=0.0)
    trail_offset: float = Field(2.0, gt=0.0)
    risk_pct: float = Field(1.0, gt=0.0)
    use_shorts: bool = True
    # Pivôs (H3)
    piv_len: int = Field(15, ge=1)
    trend_filter: bool = True

    @model_validator(mode="after")
    def _ema_fast_menor_que_slow(self) -> "EmaRsiV2Params":
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast deve ser menor que ema_slow")
        return self


def load_strategy_params(path: Path = DEFAULT_PARAMS_PATH) -> EmaRsiV2Params:
    """Carrega os defaults de config/strategies/ema_rsi_v2.yaml."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return EmaRsiV2Params(**raw["defaults"])


def crossover(series: pd.Series, level: float | pd.Series) -> pd.Series:
    """`series` cruza para cima: series[t] > level[t] E series[t-1] <= level[t].

    Para nível escalar é a semântica exata do Pine ta.crossover (spec §4.4);
    para nível em série (pivôs, H3), ambas as comparações usam o nível
    vigente em t (spec §5). NaN em qualquer lado -> False.
    """
    return (series > level) & (series.shift(1) <= level)


def crossunder(series: pd.Series, level: float | pd.Series) -> pd.Series:
    """Espelho de crossover: series[t] < level[t] E series[t-1] >= level[t]."""
    return (series < level) & (series.shift(1) >= level)


def local_trend(close: pd.Series, fast_len: int, slow_len: int) -> tuple[pd.Series, pd.Series]:
    """Tendência local 1h (spec §4.1): (uptrend, downtrend) booleanas."""
    fast, slow = ema(close, fast_len), ema(close, slow_len)
    uptrend = (fast > slow) & (close > slow)
    downtrend = (fast < slow) & (close < slow)
    return uptrend, downtrend


_HTF_PERIODS = {"D": pd.Timedelta(days=1), "W": pd.Timedelta(days=7)}


def htf_trend(close: pd.Series, timeframe: str, ema_len: int, lag: int = 1) -> pd.Series:
    """Tendência (+1/-1/0) do timeframe maior na grade 1h, sem look-ahead (spec §4.2).

    O candle HTF iniciado em S fecha em S+período e só é usado por barras 1h
    com abertura >= S + lag*período (lag=1: último candle fechado; lag=2:
    réplica do `request.security(close[1], lookahead_off)` histórico do TV).
    Semana fecha domingo 23:59 -> segunda 00:00 UTC (padrão TV p/ cripto).
    Warm-up sem candle HTF disponível -> 0 (bloqueia sinais).
    """
    if timeframe == "W":
        htf_close = close.resample("W-MON", closed="left", label="left").last()
    elif timeframe == "D":
        htf_close = close.resample("1D").last()
    else:
        raise ValueError(f"timeframe HTF inválido: {timeframe!r} (use 'D' ou 'W')")

    trend = np.sign(htf_close - ema(htf_close, ema_len))
    usable_from = htf_close.index + lag * _HTF_PERIODS[timeframe]
    return trend.set_axis(usable_from).reindex(close.index, method="ffill").fillna(0.0)


def volume_ok(volume: pd.Series, ma_len: int, mult: float) -> pd.Series:
    """Filtro de volume (spec §4.3): volume > SMA(volume, ma_len) * mult."""
    return volume > sma(volume, ma_len) * mult
