"""N1 — Donchian breakout (estilo Turtle), ciclo v3.

Fonte de retorno: tendência (time-series momentum, o efeito mais documentado
em cripto — ver docs/pesquisa-estrategias-v3.md). Regras CONGELADAS:

- Entrada long: close rompe o topo do canal de `entry_len` candles ANTERIORES
  (close[t] > highest(high, entry_len)[t-1]); short = espelho no fundo.
- Saída por canal (estilo Turtle): long sai quando close perfura o fundo do
  canal de `exit_len` (< entry_len) candles anteriores; short = espelho.
- Stop de proteção: stop_mult × ATR (no motor). Sem alvo fixo (tp_mult = 0):
  a saída é só por canal de saída ou stop — deixar o lucro correr é a
  essência do trend following.
- Filtro de regime diário opcional (daily_filter): só long se a tendência do
  Diário (EMA htf_ema_len) for de alta; só short se de baixa.

Funções puras, sem look-ahead: tudo usa .shift(1) ou janelas até t.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from cryptobot.indicators import atr, donchian_high, donchian_low
from cryptobot.strategy.base import htf_trend


class DonchianParams(BaseModel):
    """Parâmetros da família N1 (defaults = Turtle 20/10 com filtro diário)."""

    entry_len: int = Field(20, ge=2)
    exit_len: int = Field(10, ge=1)
    atr_len: int = Field(14, ge=1)
    stop_mult: float = Field(2.0, gt=0.0)
    tp_mult: float = Field(0.0, ge=0.0)  # 0 = sem alvo fixo (saída por canal/stop)
    risk_pct: float = Field(1.0, gt=0.0)
    use_shorts: bool = True
    daily_filter: bool = True
    htf_ema_len: int = Field(50, ge=1)
    htf_lag: int = Field(1, ge=1, le=2)
    # campos de execução não usados por esta família (o motor os lê)
    use_trailing: bool = False
    trail_trigger: float = Field(1.5, gt=0.0)
    trail_offset: float = Field(2.0, gt=0.0)

    @model_validator(mode="after")
    def _exit_menor_que_entry(self) -> "DonchianParams":
        if self.exit_len >= self.entry_len:
            raise ValueError("exit_len deve ser menor que entry_len (canal de saída mais curto)")
        return self


def donchian_signals(candles: pd.DataFrame, params: DonchianParams) -> pd.DataFrame:
    """Rompimento de canal -> entradas; canal oposto curto -> saídas por sinal."""
    high, low, close = candles["high"], candles["low"], candles["close"]

    entry_upper = donchian_high(high, params.entry_len).shift(1)
    entry_lower = donchian_low(low, params.entry_len).shift(1)
    exit_lower = donchian_low(low, params.exit_len).shift(1)
    exit_upper = donchian_high(high, params.exit_len).shift(1)

    long_entry = close > entry_upper
    short_entry = close < entry_lower
    long_exit = close < exit_lower
    short_exit = close > exit_upper

    if params.daily_filter:
        trend = htf_trend(close, "D", params.htf_ema_len, params.htf_lag)
        long_entry &= trend == 1
        short_entry &= trend == -1

    if not params.use_shorts:
        short_entry = pd.Series(False, index=candles.index)

    signal_atr = atr(high, low, close, params.atr_len)
    valid = signal_atr.notna() & entry_upper.notna()
    return pd.DataFrame(
        {
            "long_entry": long_entry & valid,
            "short_entry": short_entry & valid,
            "long_exit": long_exit.fillna(False),
            "short_exit": short_exit.fillna(False),
            "atr": signal_atr,
        }
    )
