"""T0.2 — Smoke test do stack de backtest (vectorbt + numba + pandas + pyarrow).

Roda um backtest dummy sobre 1.000 candles sintéticos de 1h com custos,
exercitando o caminho que o motor real (T1.4) vai usar:
DataFrame OHLCV -> sinais booleanos -> Portfolio.from_signals -> métricas.

Sai com código 0 se tudo funcionar; qualquer exceção = stack incompatível.
"""

import sys

import numpy as np
import pandas as pd


def make_synthetic_candles(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(loc=0.0, scale=0.01, size=n)
    close = 50_000.0 * np.exp(np.cumsum(log_returns))
    high = close * (1 + rng.uniform(0, 0.005, size=n))
    low = close * (1 - rng.uniform(0, 0.005, size=n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = rng.uniform(100, 1000, size=n)
    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def main() -> int:
    import vectorbt as vbt

    candles = make_synthetic_candles()
    close = candles["close"]

    fast = close.ewm(span=10, adjust=False).mean()
    slow = close.ewm(span=30, adjust=False).mean()
    entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
    exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))

    pf = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=10_000,
        fees=0.00055,      # taker 0.055%
        slippage=0.0001,
        freq="1h",
    )

    n_trades = int(pf.trades.count())
    total_return = float(pf.total_return())
    total_fees = float(pf.orders.records_readable["Fees"].sum())

    assert n_trades > 0, "backtest dummy deveria gerar trades"
    assert total_fees > 0, "custos deveriam ser aplicados"
    assert np.isfinite(total_return), "retorno deveria ser um número finito"

    # Round-trip Parquet (pyarrow) — caminho usado pelo cache de dados
    candles.to_parquet("_smoke_test.parquet")
    recovered = pd.read_parquet("_smoke_test.parquet")
    # check_freq=False: Parquet não preserva o metadado freq do índice (esperado)
    pd.testing.assert_frame_equal(candles, recovered, check_freq=False)
    import os

    os.remove("_smoke_test.parquet")

    print(f"vectorbt {vbt.__version__} OK no Python {sys.version.split()[0]}")
    print(f"trades: {n_trades} | retorno total: {total_return:+.2%} | fees: {total_fees:.2f}")
    print("parquet round-trip OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
