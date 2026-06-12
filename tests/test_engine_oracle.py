"""T1.5 — Oráculo independente do motor: simulador ingênuo da spec.

A configuração exata do run de referência do TradingView se perdeu (ver
docs/calibracao-t1.5.md), então a confiança no motor vem de duas frentes:
cenários à mão (test_engine.py) e ESTE oráculo — uma segunda implementação
da spec §2/§4.6-§4.7, propositalmente ingênua e com ramos long/short
explícitos (estrutura diferente da álgebra d=+1/-1 do motor numba). Os dois
precisam concordar trade a trade e barra a barra.
"""

import numpy as np
import pandas as pd
import pytest

from cryptobot.backtest import run_backtest
from cryptobot.backtest.funding import funding_on_grid
from cryptobot.config import BacktestConfig
from cryptobot.strategy import EmaRsiV2Params, ema_rsi_signals

CONFIG = BacktestConfig(initial_capital=10_000.0, tick_size={"X": 0.1, "BTCUSDT": 0.1})


def simulate_oracle(candles, signals, params, config, symbol, funding=None):
    """Transcrição direta e legível da spec — sem otimização, sem álgebra."""
    fee_rate = config.taker_fee
    slip = config.slippage(symbol)
    rates = (
        funding_on_grid(candles.index, funding)
        if funding is not None
        else pd.Series(0.0, index=candles.index)
    )
    o = candles["open"].to_numpy()
    h = candles["high"].to_numpy()
    lo = candles["low"].to_numpy()
    c = candles["close"].to_numpy()
    long_sig = signals["long_entry"].to_numpy()
    short_sig = signals["short_entry"].to_numpy()
    atr = signals["atr"].to_numpy()
    fr = rates.to_numpy()

    cash = config.initial_capital
    pos = None
    trades = []
    equity = np.empty(len(c))

    def close_position(t, price, reason):
        nonlocal cash, pos
        exit_fee = fee_rate * pos["qty"] * price
        if pos["side"] == "long":
            cash += pos["qty"] * (price - pos["entry_price"]) - exit_fee
        else:
            cash += pos["qty"] * (pos["entry_price"] - price) - exit_fee
        trades.append(
            {
                "entry_idx": pos["entry_bar"],
                "exit_idx": t,
                "side": pos["side"],
                "qty": pos["qty"],
                "entry_price": pos["entry_price"],
                "exit_price": price,
                "fees": pos["fees"] + exit_fee,
                "funding": pos["funding"],
                "reason": reason,
            }
        )
        pos = None

    for t in range(len(c)):
        # 1) funding sobre posição carregada
        if pos is not None and pos["entry_bar"] < t and fr[t] != 0.0:
            if pos["side"] == "long":
                pay = fr[t] * pos["qty"] * o[t]
            else:
                pay = -fr[t] * pos["qty"] * o[t]
            cash -= pay
            pos["funding"] += pay

        # 2) entrada pendente do sinal de t-1
        if pos is None and t > 0 and cash > 0 and (long_sig[t - 1] or short_sig[t - 1]):
            dist = params.stop_mult * atr[t - 1]
            if dist > 0:
                side = "long" if long_sig[t - 1] else "short"
                if side == "long":
                    fill = o[t] + slip
                    stop = c[t - 1] - dist
                    tp = c[t - 1] + params.tp_mult * atr[t - 1]
                    activation = fill + params.trail_trigger * atr[t - 1]
                else:
                    fill = o[t] - slip
                    stop = c[t - 1] + dist
                    tp = c[t - 1] - params.tp_mult * atr[t - 1]
                    activation = fill - params.trail_trigger * atr[t - 1]
                qty = cash * (params.risk_pct / 100.0) / dist
                entry_fee = fee_rate * qty * fill
                cash -= entry_fee
                pos = {
                    "side": side,
                    "qty": qty,
                    "entry_price": fill,
                    "entry_bar": t,
                    "stop": stop,
                    "tp": tp,
                    "activation": activation,
                    "off": params.trail_offset * atr[t - 1],
                    "trail": None,
                    "fees": entry_fee,
                    "funding": 0.0,
                }

        # 3) saídas — pior caso: stop fixo primeiro
        if pos is not None and pos["side"] == "long":
            if lo[t] <= pos["stop"]:
                close_position(t, min(o[t], pos["stop"]) - slip, "stop")
            elif params.use_trailing:
                if pos["trail"] is None:
                    if h[t] >= pos["activation"]:
                        pos["trail"] = h[t] - pos["off"]
                else:
                    pos["trail"] = max(pos["trail"], h[t] - pos["off"])
                if pos is not None and pos["trail"] is not None and lo[t] <= pos["trail"]:
                    close_position(t, min(o[t], pos["trail"]) - slip, "trail")
            elif h[t] >= pos["tp"]:
                close_position(t, max(o[t], pos["tp"]), "tp")
        elif pos is not None:
            if h[t] >= pos["stop"]:
                close_position(t, max(o[t], pos["stop"]) + slip, "stop")
            elif params.use_trailing:
                if pos["trail"] is None:
                    if lo[t] <= pos["activation"]:
                        pos["trail"] = lo[t] + pos["off"]
                else:
                    pos["trail"] = min(pos["trail"], lo[t] + pos["off"])
                if pos is not None and pos["trail"] is not None and h[t] >= pos["trail"]:
                    close_position(t, max(o[t], pos["trail"]) + slip, "trail")
            elif lo[t] <= pos["tp"]:
                close_position(t, min(o[t], pos["tp"]), "tp")

        # 4) equity a mercado no close
        if pos is None:
            equity[t] = cash
        elif pos["side"] == "long":
            equity[t] = cash + pos["qty"] * (c[t] - pos["entry_price"])
        else:
            equity[t] = cash + pos["qty"] * (pos["entry_price"] - c[t])

    # 5) fim dos dados
    if pos is not None:
        last = len(c) - 1
        price = c[last] - slip if pos["side"] == "long" else c[last] + slip
        close_position(last, price, "end_of_data")
        equity[last] = cash

    return pd.Series(equity, index=candles.index), pd.DataFrame(trades)


@pytest.fixture(scope="module")
def candles() -> pd.DataFrame:
    rng = np.random.default_rng(123)
    n = 3000  # ~4 meses de 1h
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(20_000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx)
    spread = close * rng.uniform(0.001, 0.01, n)
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "open": open_,
            "high": pd.concat([open_, close], axis=1).max(axis=1) + spread,
            "low": pd.concat([open_, close], axis=1).min(axis=1) - spread,
            "close": close,
            "volume": pd.Series(rng.uniform(10, 1000, n), index=idx),
        }
    )


@pytest.fixture(scope="module")
def funding_sintetico(candles) -> pd.Series:
    grid = candles.index[candles.index.hour.isin([0, 8, 16])]
    rng = np.random.default_rng(9)
    return pd.Series(rng.normal(0.0001, 0.0003, len(grid)), index=grid)


def _comparar(candles, signals, params, funding):
    motor = run_backtest(candles, signals, params, CONFIG, "X", funding=funding)
    eq_oraculo, tr_oraculo = simulate_oracle(
        candles, signals, params, CONFIG, "X", funding=funding
    )

    assert motor.n_trades == len(tr_oraculo) > 0
    np.testing.assert_allclose(motor.equity.to_numpy(), eq_oraculo.to_numpy(), rtol=1e-12)
    for col in ["qty", "entry_price", "exit_price", "fees", "funding"]:
        np.testing.assert_allclose(
            motor.trades[col].to_numpy(), tr_oraculo[col].to_numpy(), rtol=1e-12
        )
    assert motor.trades["reason"].tolist() == tr_oraculo["reason"].tolist()
    assert motor.trades["side"].tolist() == tr_oraculo["side"].tolist()
    assert [candles.index.get_loc(t) for t in motor.trades["entry_time"]] == tr_oraculo[
        "entry_idx"
    ].tolist()
    assert [candles.index.get_loc(t) for t in motor.trades["exit_time"]] == tr_oraculo[
        "exit_idx"
    ].tolist()


PARAMS_CURTOS = dict(
    ema_fast=10, ema_slow=30, rsi_len=7, atr_len=7,
    use_daily=False, use_weekly=False, use_vol_filter=False,
)


def test_motor_igual_oraculo_alvo_fixo(candles, funding_sintetico):
    params = EmaRsiV2Params(**PARAMS_CURTOS)
    signals = ema_rsi_signals(candles, params)
    _comparar(candles, signals, params, funding_sintetico)


def test_motor_igual_oraculo_trailing(candles, funding_sintetico):
    params = EmaRsiV2Params(**PARAMS_CURTOS, use_trailing=True)
    signals = ema_rsi_signals(candles, params)
    _comparar(candles, signals, params, funding_sintetico)


def test_motor_igual_oraculo_dados_reais():
    """BTCUSDT real, baseline default, com funding real (skip sem cache)."""
    from cryptobot.config import load_data_config
    from cryptobot.data.downloader import funding_path, kline_path

    cfg = load_data_config()
    kpath, fpath = kline_path(cfg.data_dir, "BTCUSDT"), funding_path(cfg.data_dir, "BTCUSDT")
    if not kpath.exists() or not fpath.exists():
        pytest.skip("cache de dados ausente (rode scripts/download_data.py)")

    candles = pd.read_parquet(kpath)
    funding = pd.read_parquet(fpath)["funding_rate"]
    params = EmaRsiV2Params(use_daily=False, use_weekly=False, use_vol_filter=False)
    signals = ema_rsi_signals(candles, params)
    janela = slice("2024-01-01", None)
    _comparar(candles.loc[janela], signals.loc[janela], params, funding)
