"""T1.6 — Relatório padrão: artefatos completos + reprodutibilidade (RF-007)."""

import json

import numpy as np
import pandas as pd
import pytest

from cryptobot.backtest import experiment_report, run_backtest
from cryptobot.config import BacktestConfig
from cryptobot.strategy import EmaRsiV2Params, ema_rsi_signals

CONFIG = BacktestConfig(initial_capital=10_000.0, tick_size={"X": 0.1})
PARAMS = EmaRsiV2Params(
    ema_fast=10, ema_slow=30, rsi_len=7, atr_len=7,
    use_daily=False, use_weekly=False, use_vol_filter=False,
)


@pytest.fixture(scope="module")
def resultado():
    rng = np.random.default_rng(11)
    n = 2000
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(20_000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx)
    spread = close * rng.uniform(0.001, 0.01, n)
    open_ = close.shift(1).fillna(close.iloc[0])
    candles = pd.DataFrame(
        {
            "open": open_,
            "high": pd.concat([open_, close], axis=1).max(axis=1) + spread,
            "low": pd.concat([open_, close], axis=1).min(axis=1) - spread,
            "close": close,
            "volume": pd.Series(rng.uniform(10, 1000, n), index=idx),
        }
    )
    signals = ema_rsi_signals(candles, PARAMS)
    return run_backtest(candles, signals, PARAMS, CONFIG, "X")


def test_relatorio_gera_artefatos(resultado, tmp_path):
    rdir = experiment_report(resultado, "teste-exp", "X", PARAMS, CONFIG, out_dir=tmp_path)

    assert (rdir / "metrics.json").exists()
    assert (rdir / "equity.png").stat().st_size > 1000
    assert (rdir / "trades.csv").exists()

    payload = json.loads((rdir / "metrics.json").read_text(encoding="utf-8"))
    assert payload["experiment"] == "teste-exp"
    assert payload["symbol"] == "X"
    metricas = payload["metrics"]
    for chave in (
        "n_trades", "profit_factor", "max_drawdown", "sharpe",
        "win_rate", "total_return", "total_fees", "total_funding",
    ):
        assert chave in metricas, f"métrica ausente: {chave}"
    assert metricas["n_trades"] == resultado.n_trades
    assert payload["params"]["ema_fast"] == 10
    assert payload["backtest_config"]["initial_capital"] == 10_000.0
    assert len(payload["git"]["commit"]) in (7, 40) or payload["git"]["commit"] == "unknown"

    trades = pd.read_csv(rdir / "trades.csv")
    assert len(trades) == resultado.n_trades


def test_reprodutibilidade_mesma_config_numeros_identicos(resultado, tmp_path):
    """VERIFY do T1.6: dois relatórios da mesma config -> métricas idênticas."""
    dir_a = experiment_report(resultado, "rep-a", "X", PARAMS, CONFIG, out_dir=tmp_path)
    dir_b = experiment_report(resultado, "rep-b", "X", PARAMS, CONFIG, out_dir=tmp_path)

    a = json.loads((dir_a / "metrics.json").read_text(encoding="utf-8"))
    b = json.loads((dir_b / "metrics.json").read_text(encoding="utf-8"))
    for volatil in ("generated_at", "experiment"):
        a.pop(volatil), b.pop(volatil)
    assert a == b


def test_sharpe_sinal_coerente():
    idx = pd.date_range("2024-01-01", periods=200, freq="h", tz="UTC")
    from cryptobot.backtest import BacktestResult

    subida = BacktestResult(
        equity=pd.Series(np.linspace(10_000, 11_000, 200) * (1 + 1e-4 * np.sin(range(200))),
                         index=idx),
        trades=pd.DataFrame(columns=["pnl", "fees", "funding"]),
        initial_capital=10_000.0,
    )
    assert subida.sharpe > 0
    plana = BacktestResult(
        equity=pd.Series(10_000.0, index=idx),
        trades=pd.DataFrame(columns=["pnl", "fees", "funding"]),
        initial_capital=10_000.0,
    )
    assert np.isnan(plana.sharpe)
