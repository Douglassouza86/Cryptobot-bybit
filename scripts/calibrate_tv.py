"""T1.5 — Calibração do motor contra o resultado conhecido do TradingView.

Réplica da estratégia baseline (v1: sem MTF, sem volume, alvo fixo) em
BTCUSDT 1h na janela 2024->fim dos dados, SEM funding (o TV não simula).
Referência do TV: PF ~= 0.716, ~132 trades.
Critério (plano): mesma direção (PF < 1) e ordem de grandeza (trades +-20%);
divergências explicadas pela spec §8.

Indicadores são calculados sobre o histórico COMPLETO (como no gráfico do
TV, que tem dados antes da janela) e só a execução é recortada na janela.

Uso: uv run python scripts/calibrate_tv.py [--start 2024-01-01] [--end ...]
"""

import argparse

import pandas as pd

from cryptobot.backtest import run_backtest
from cryptobot.config import load_backtest_config, load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.strategy import EmaRsiV2Params, ema_rsi_signals

TV_REF = {"profit_factor": 0.716, "n_trades": 132}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args()

    data_cfg = load_data_config()
    bt_cfg = load_backtest_config()

    candles = pd.read_parquet(kline_path(data_cfg.data_dir, args.symbol))
    funding = pd.read_parquet(funding_path(data_cfg.data_dir, args.symbol))["funding_rate"]

    # baseline v1: núcleo EMA+RSI puro (H1), alvo fixo
    params = EmaRsiV2Params(use_daily=False, use_weekly=False, use_vol_filter=False)
    signals = ema_rsi_signals(candles, params)  # indicadores aquecidos no histórico todo

    window = slice(args.start, args.end)
    candles_w, signals_w = candles.loc[window], signals.loc[window]
    print(f"{args.symbol} 1h — janela {candles_w.index[0]} -> {candles_w.index[-1]}")
    print(f"({len(candles_w)} candles; sinais: {int(signals_w['long_entry'].sum())} long, "
          f"{int(signals_w['short_entry'].sum())} short)\n")

    replica = run_backtest(candles_w, signals_w, params, bt_cfg, args.symbol, funding=None)
    com_funding = run_backtest(
        candles_w, signals_w, params, bt_cfg, args.symbol, funding=funding
    )

    linhas = [
        ("TradingView (referência)", TV_REF["profit_factor"], TV_REF["n_trades"], None, None),
        ("Motor (réplica TV, sem funding)", replica.profit_factor, replica.n_trades,
         replica.max_drawdown, replica.win_rate),
        ("Motor (produção, com funding)", com_funding.profit_factor, com_funding.n_trades,
         com_funding.max_drawdown, com_funding.win_rate),
    ]
    print(f"{'':36} {'PF':>7} {'trades':>7} {'DD máx':>8} {'win%':>6}")
    for nome, pf, n, dd, wr in linhas:
        dd_s = f"{dd:8.1%}" if dd is not None else f"{'—':>8}"
        wr_s = f"{wr:6.1%}" if wr is not None else f"{'—':>6}"
        print(f"{nome:36} {pf:7.3f} {n:7d} {dd_s} {wr_s}")

    pf_ok = replica.profit_factor < 1.0
    lo, hi = TV_REF["n_trades"] * 0.8, TV_REF["n_trades"] * 1.2
    trades_ok = lo <= replica.n_trades <= hi
    print(f"\nPF < 1 (mesma direção do TV): {'OK' if pf_ok else 'FALHOU'}")
    print(f"Trades em [{lo:.0f}, {hi:.0f}] (±20% de {TV_REF['n_trades']}): "
          f"{'OK' if trades_ok else 'FALHOU'} ({replica.n_trades})")
    print(f"Efeito do funding no PF: {replica.profit_factor:.3f} -> "
          f"{com_funding.profit_factor:.3f}")
    print(f"\nCALIBRAÇÃO: {'APROVADA' if pf_ok and trades_ok else 'REPROVADA'}")


if __name__ == "__main__":
    main()
