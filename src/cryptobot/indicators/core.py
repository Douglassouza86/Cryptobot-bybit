"""Indicadores técnicos como funções puras (RF-006).

Semântica idêntica à do Pine Script v5 (`ta.ema`, `ta.rma`, `ta.rsi`,
`ta.atr`, `ta.sma`, `ta.pivothigh`/`ta.pivotlow`) — ver docs/strategy-v2-spec.md §3.
O mesmo código serve backtest e executor; o valor em `t` depende apenas de
dados `<= t` (sem look-ahead).

Pré-condição: séries sem NaN internos (garantido pela integridade da Fase 0);
NaN apenas no início (warm-up) é suportado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def ema(series: pd.Series, length: int) -> pd.Series:
    """EMA com alpha = 2/(length+1), semente no primeiro valor (Pine ta.ema)."""
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    """Média móvel simples; NaN antes de `length` valores (Pine ta.sma)."""
    return series.rolling(length, min_periods=length).mean()


def rma(series: pd.Series, length: int) -> pd.Series:
    """Média de Wilder: alpha = 1/length, semente = SMA dos primeiros
    `length` valores válidos (Pine ta.rma). NaN antes da semente."""
    arr = series.to_numpy(dtype=np.float64)
    valid = ~np.isnan(arr)
    if not valid.any():
        return pd.Series(np.nan, index=series.index)
    first = int(np.argmax(valid))
    seed_idx = first + length - 1
    if seed_idx >= len(arr):
        return pd.Series(np.nan, index=series.index)

    prepped = np.full(len(arr), np.nan)
    prepped[seed_idx] = arr[first : seed_idx + 1].mean()
    prepped[seed_idx + 1 :] = arr[seed_idx + 1 :]
    return pd.Series(prepped, index=series.index).ewm(alpha=1.0 / length, adjust=False).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI de Wilder: 100 * rma(up) / (rma(up) + rma(down)) (Pine ta.rsi).

    Forma sem divisão por zero: só altas -> 100, só baixas -> 0.
    """
    delta = close.diff()
    avg_up = rma(delta.clip(lower=0.0), length)
    avg_down = rma((-delta).clip(lower=0.0), length)
    return 100.0 * avg_up / (avg_up + avg_down)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range; na primeira barra (sem close anterior) vale high - low."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    tr.iloc[0] = high.iloc[0] - low.iloc[0]
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """ATR = rma(true_range, length) (Pine ta.atr)."""
    return rma(true_range(high, low, close), length)


def _pivot(series: pd.Series, left: int, right: int, is_high: bool) -> pd.Series:
    arr = series.to_numpy(dtype=np.float64)
    out = np.full(len(arr), np.nan)
    window = left + right + 1
    if left < 1 or right < 1 or len(arr) < window:
        return pd.Series(out, index=series.index)

    views = sliding_window_view(arr, window)
    center = views[:, left]
    if is_high:
        ok = (center > views[:, :left].max(axis=1)) & (center > views[:, left + 1 :].max(axis=1))
    else:
        ok = (center < views[:, :left].min(axis=1)) & (center < views[:, left + 1 :].min(axis=1))
    # valor disponível apenas na barra de confirmação (pivô + right barras)
    out[window - 1 :][ok] = center[ok]
    return pd.Series(out, index=series.index)


def pivot_high(high: pd.Series, left: int, right: int) -> pd.Series:
    """Pine ta.pivothigh: preço do pivô na barra de CONFIRMAÇÃO (`right`
    barras após o pivô), NaN nas demais. Exige máximo estrito — platôs com
    valores iguais não geram pivô."""
    return _pivot(high, left, right, is_high=True)


def pivot_low(low: pd.Series, left: int, right: int) -> pd.Series:
    """Pine ta.pivotlow: espelho de pivot_high para mínimas."""
    return _pivot(low, left, right, is_high=False)
