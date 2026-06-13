"""Núcleo de sinal da família v2 (T1.3, RF-006) — candles -> sinais.

Funções puras, sem look-ahead, compartilhadas entre backtest e executor.
Saída no contrato SIGNAL_COLUMNS (spec §4.5/§5): sinal marcado no candle em
que as condições fecham; a execução na abertura do candle seguinte, stops,
alvos, trailing e sizing são responsabilidade do motor (T1.4, spec §4.6-§4.7).
"""

from __future__ import annotations

import pandas as pd

from cryptobot.indicators import atr, pivot_high, pivot_low, rsi
from cryptobot.strategy.base import (
    EmaRsiV2Params,
    crossover,
    crossunder,
    htf_trend,
    local_trend,
    volume_ok,
)


def _signal_frame(
    candles: pd.DataFrame,
    long_entry: pd.Series,
    short_entry: pd.Series,
    params: EmaRsiV2Params,
) -> pd.DataFrame:
    signal_atr = atr(candles["high"], candles["low"], candles["close"], params.atr_len)
    valid = signal_atr.notna()  # sem ATR não há stop nem sizing (spec §4.6-§4.7)
    if not params.use_shorts:
        short_entry = pd.Series(False, index=candles.index)
    return pd.DataFrame(
        {
            "long_entry": long_entry & valid,
            "short_entry": short_entry & valid,
            "atr": signal_atr,
        }
    )


def ema_rsi_signals(candles: pd.DataFrame, params: EmaRsiV2Params) -> pd.DataFrame:
    """Entrada por pullback de RSI com filtros de tendência/MTF/volume (H1/H2/H4).

    long  = uptrend   E htf_ok_long  E vol_ok E crossover(rsi, rsi_long_lvl)
    short = downtrend E htf_ok_short E vol_ok E crossunder(rsi, rsi_short_lvl)
    """
    close = candles["close"]
    uptrend, downtrend = local_trend(close, params.ema_fast, params.ema_slow)

    htf_ok_long = pd.Series(True, index=candles.index)
    htf_ok_short = pd.Series(True, index=candles.index)
    for enabled, timeframe in ((params.use_daily, "D"), (params.use_weekly, "W")):
        if enabled:
            trend = htf_trend(close, timeframe, params.htf_ema_len, params.htf_lag)
            htf_ok_long &= trend == 1
            htf_ok_short &= trend == -1

    if params.use_vol_filter:
        vol_ok = volume_ok(candles["volume"], params.vol_ma_len, params.vol_mult)
    else:
        vol_ok = pd.Series(True, index=candles.index)

    rsi_series = rsi(close, params.rsi_len)
    long_entry = uptrend & htf_ok_long & vol_ok & crossover(rsi_series, params.rsi_long_lvl)
    short_entry = (
        downtrend & htf_ok_short & vol_ok & crossunder(rsi_series, params.rsi_short_lvl)
    )
    return _signal_frame(candles, long_entry, short_entry, params)


def pivot_breakout_signals(candles: pd.DataFrame, params: EmaRsiV2Params) -> pd.DataFrame:
    """Entrada por rompimento do último pivô confirmado (H3, spec §5).

    O nível ativo nasce na barra de confirmação (pivô + piv_len barras) e
    vale a partir dela, inclusive. Sem RSI, sem MTF, sem volume; filtro de
    tendência local opcional (params.trend_filter).
    """
    close = candles["close"]
    resistance = pivot_high(candles["high"], params.piv_len, params.piv_len).ffill()
    support = pivot_low(candles["low"], params.piv_len, params.piv_len).ffill()

    long_entry = crossover(close, resistance)
    short_entry = crossunder(close, support)
    if params.trend_filter:
        uptrend, downtrend = local_trend(close, params.ema_fast, params.ema_slow)
        long_entry &= uptrend
        short_entry &= downtrend
    return _signal_frame(candles, long_entry, short_entry, params)
