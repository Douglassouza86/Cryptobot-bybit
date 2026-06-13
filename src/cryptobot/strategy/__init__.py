"""Núcleo de estratégia: funções puras candles → sinais (RF-006)."""

from cryptobot.strategy.base import (
    SIGNAL_COLUMNS,
    EmaRsiV2Params,
    crossover,
    crossunder,
    htf_trend,
    load_strategy_params,
    local_trend,
    volume_ok,
)
from cryptobot.strategy.donchian import DonchianParams, donchian_signals
from cryptobot.strategy.ema_rsi_v2 import ema_rsi_signals, pivot_breakout_signals
from cryptobot.strategy.registry import FAMILIES, StrategyFamily, get_family

__all__ = [
    "FAMILIES",
    "SIGNAL_COLUMNS",
    "DonchianParams",
    "EmaRsiV2Params",
    "StrategyFamily",
    "crossover",
    "crossunder",
    "donchian_signals",
    "ema_rsi_signals",
    "get_family",
    "htf_trend",
    "load_strategy_params",
    "local_trend",
    "pivot_breakout_signals",
    "volume_ok",
]
