"""Motor de backtest com custos completos (T1.4, RF-003).

Laço de eventos próprio (acelerado com numba) que implementa EXATAMENTE a
semântica congelada em docs/strategy-v2-spec.md §2/§4.6-§4.7 — o
`vectorbt.from_signals` não expressa trailing com gatilho de ativação,
pior caso stop-primeiro, funding alterando o equity e sizing por risco,
então o vectorbt fica como ferramenta de análise, não como motor.

Convenções (spec §2):
- sinal no fechamento de t, entrada a mercado na abertura de t+1 (+ slippage);
- stop/alvo/trailing congelados no close e ATR do candle do SINAL;
- slippage em market/stop, zero em limit; gaps: stop preenche no pior entre
  abertura e nível, limit no melhor;
- stop e alvo no mesmo candle -> pior caso (stop primeiro);
- funding cobrado na abertura da barra do evento sobre posição carregada;
- 1 posição por par; posição aberta no fim dos dados é fechada a mercado
  no último close.

Toda a aritmética usa d = +1 (long) / -1 (short) para espelhar as regras.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import njit

from cryptobot.backtest.funding import funding_on_grid
from cryptobot.config import BacktestConfig
from cryptobot.strategy.base import EmaRsiV2Params

REASON_LABELS = {0: "stop", 1: "tp", 2: "trail", 3: "end_of_data"}


def _simulate_py(  # noqa: PLR0912, PLR0915 - laço de simulação é naturalmente ramificado
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    long_entry: np.ndarray,
    short_entry: np.ndarray,
    atr_arr: np.ndarray,
    funding_rate: np.ndarray,
    init_cash: float,
    fee_rate: float,
    slip: float,
    risk_pct: float,
    stop_mult: float,
    tp_mult: float,
    use_trailing: bool,
    trail_trigger: float,
    trail_offset: float,
):
    n = len(open_)
    equity = np.empty(n, dtype=np.float64)

    # buffers de trades (máx. 1 entrada por barra)
    tr_entry_idx = np.empty(n, dtype=np.int64)
    tr_exit_idx = np.empty(n, dtype=np.int64)
    tr_side = np.empty(n, dtype=np.int64)
    tr_qty = np.empty(n, dtype=np.float64)
    tr_entry_price = np.empty(n, dtype=np.float64)
    tr_exit_price = np.empty(n, dtype=np.float64)
    tr_fees = np.empty(n, dtype=np.float64)
    tr_funding = np.empty(n, dtype=np.float64)
    tr_reason = np.empty(n, dtype=np.int64)
    k = 0

    cash = init_cash
    d = 0  # direção corrente: 0 = zerado
    qty = 0.0
    entry_price = 0.0
    stop_price = 0.0
    tp_price = 0.0
    activation = 0.0
    off_dist = 0.0
    trail_stop = 0.0
    trail_active = False
    entry_idx = -1
    fees_acc = 0.0
    funding_acc = 0.0

    for t in range(n):
        o = open_[t]

        # 1) funding sobre posição carregada da barra anterior (spec §2)
        if d != 0 and entry_idx < t and funding_rate[t] != 0.0:
            pay = d * funding_rate[t] * qty * o
            cash -= pay
            funding_acc += pay

        # 2) entrada pendente do sinal de t-1 (execução na abertura de t)
        if d == 0 and t > 0 and cash > 0.0:
            want_long = long_entry[t - 1]
            want_short = short_entry[t - 1]
            if want_long or want_short:
                stop_dist = stop_mult * atr_arr[t - 1]
                if stop_dist > 0.0:
                    d = 1 if want_long else -1  # empate (impossível no núcleo): long
                    entry_price = o + d * slip
                    qty = cash * (risk_pct / 100.0) / stop_dist
                    ref = close[t - 1]
                    stop_price = ref - d * stop_dist
                    tp_price = ref + d * tp_mult * atr_arr[t - 1]
                    activation = entry_price + d * trail_trigger * atr_arr[t - 1]
                    off_dist = trail_offset * atr_arr[t - 1]
                    trail_active = False
                    trail_stop = 0.0
                    fee = fee_rate * qty * entry_price
                    cash -= fee
                    fees_acc = fee
                    funding_acc = 0.0
                    entry_idx = t

        # 3) saídas (inclusive na barra da entrada)
        if d != 0:
            adverse = low[t] if d == 1 else high[t]
            favorable = high[t] if d == 1 else low[t]
            exit_price = 0.0
            reason = -1

            # pior caso: stop fixo primeiro (spec §2)
            if (adverse - stop_price) * d <= 0.0:
                base = o if (o - stop_price) * d < 0.0 else stop_price
                exit_price = base - d * slip
                reason = 0
            elif use_trailing:
                if not trail_active:
                    if (favorable - activation) * d >= 0.0:
                        trail_active = True
                        trail_stop = favorable - d * off_dist
                else:
                    cand = favorable - d * off_dist
                    if (cand - trail_stop) * d > 0.0:
                        trail_stop = cand
                if trail_active and (adverse - trail_stop) * d <= 0.0:
                    base = o if (o - trail_stop) * d < 0.0 else trail_stop
                    exit_price = base - d * slip
                    reason = 2
            else:
                if (favorable - tp_price) * d >= 0.0:
                    base = o if (o - tp_price) * d > 0.0 else tp_price  # limit: melhor preço
                    exit_price = base
                    reason = 1

            if reason >= 0:
                fee = fee_rate * qty * exit_price
                cash += d * qty * (exit_price - entry_price) - fee
                fees_acc += fee
                tr_entry_idx[k] = entry_idx
                tr_exit_idx[k] = t
                tr_side[k] = d
                tr_qty[k] = qty
                tr_entry_price[k] = entry_price
                tr_exit_price[k] = exit_price
                tr_fees[k] = fees_acc
                tr_funding[k] = funding_acc
                tr_reason[k] = reason
                k += 1
                d = 0
                qty = 0.0

        # 4) equity a mercado no fechamento
        if d != 0:
            equity[t] = cash + d * qty * (close[t] - entry_price)
        else:
            equity[t] = cash

    # 5) posição aberta no fim dos dados: fecha a mercado no último close
    if d != 0:
        exit_price = close[n - 1] - d * slip
        fee = fee_rate * qty * exit_price
        cash += d * qty * (exit_price - entry_price) - fee
        fees_acc += fee
        tr_entry_idx[k] = entry_idx
        tr_exit_idx[k] = n - 1
        tr_side[k] = d
        tr_qty[k] = qty
        tr_entry_price[k] = entry_price
        tr_exit_price[k] = exit_price
        tr_fees[k] = fees_acc
        tr_funding[k] = funding_acc
        tr_reason[k] = 3
        k += 1
        equity[n - 1] = cash

    return (
        equity,
        tr_entry_idx[:k],
        tr_exit_idx[:k],
        tr_side[:k],
        tr_qty[:k],
        tr_entry_price[:k],
        tr_exit_price[:k],
        tr_fees[:k],
        tr_funding[:k],
        tr_reason[:k],
    )


_simulate = njit(cache=True)(_simulate_py)


@dataclass
class BacktestResult:
    """Curva de equity (marcada no close) + trades com custos por trade."""

    equity: pd.Series
    trades: pd.DataFrame
    initial_capital: float

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def profit_factor(self) -> float:
        pnl = self.trades["pnl"]
        wins = pnl[pnl > 0].sum()
        losses = -pnl[pnl < 0].sum()
        if losses == 0.0:
            return float("inf") if wins > 0 else float("nan")
        return float(wins / losses)

    @property
    def max_drawdown(self) -> float:
        """Drawdown máximo da curva de equity, como fração positiva."""
        dd = self.equity / self.equity.cummax() - 1.0
        return float(-dd.min())

    @property
    def win_rate(self) -> float:
        if not self.n_trades:
            return float("nan")
        return float((self.trades["pnl"] > 0).mean())

    @property
    def total_return(self) -> float:
        return float(self.equity.iloc[-1] / self.initial_capital - 1.0)

    @property
    def total_fees(self) -> float:
        return float(self.trades["fees"].sum())

    @property
    def total_funding(self) -> float:
        return float(self.trades["funding"].sum())

    def summary(self) -> dict:
        return {
            "n_trades": self.n_trades,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_return": self.total_return,
            "total_fees": self.total_fees,
            "total_funding": self.total_funding,
            "final_equity": float(self.equity.iloc[-1]),
        }


def run_backtest(
    candles: pd.DataFrame,
    signals: pd.DataFrame,
    params: EmaRsiV2Params,
    config: BacktestConfig,
    symbol: str,
    funding: pd.Series | None = None,
) -> BacktestResult:
    """Executa a simulação sobre candles + sinais (contrato SIGNAL_COLUMNS).

    `funding` é a série 8h do cache; None = sem funding (ex.: réplica do TV
    na calibração T1.5).
    """
    if funding is not None:
        funding_rate = funding_on_grid(candles.index, funding).to_numpy(dtype=np.float64)
    else:
        funding_rate = np.zeros(len(candles), dtype=np.float64)

    out = _simulate(
        candles["open"].to_numpy(dtype=np.float64),
        candles["high"].to_numpy(dtype=np.float64),
        candles["low"].to_numpy(dtype=np.float64),
        candles["close"].to_numpy(dtype=np.float64),
        signals["long_entry"].to_numpy(dtype=np.bool_),
        signals["short_entry"].to_numpy(dtype=np.bool_),
        signals["atr"].to_numpy(dtype=np.float64),
        funding_rate,
        config.initial_capital,
        config.taker_fee,
        config.slippage(symbol),
        params.risk_pct,
        params.stop_mult,
        params.tp_mult,
        params.use_trailing,
        params.trail_trigger,
        params.trail_offset,
    )
    equity_arr, entry_idx, exit_idx, side, qty, entry_p, exit_p, fees, fund, reason = out

    pnl = side * qty * (exit_p - entry_p) - fees - fund
    trades = pd.DataFrame(
        {
            "entry_time": candles.index[entry_idx],
            "exit_time": candles.index[exit_idx],
            "side": np.where(side == 1, "long", "short"),
            "qty": qty,
            "entry_price": entry_p,
            "exit_price": exit_p,
            "fees": fees,
            "funding": fund,
            "pnl": pnl,
            "reason": [REASON_LABELS[r] for r in reason],
        }
    )
    equity = pd.Series(equity_arr, index=candles.index, name="equity")
    return BacktestResult(equity=equity, trades=trades, initial_capital=config.initial_capital)
