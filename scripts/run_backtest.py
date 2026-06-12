"""Roda um backtest único e gera o relatório padrão (T1.6, RF-007).

Uso:
  uv run python scripts/run_backtest.py --symbol BTCUSDT --name h1-default
  uv run python scripts/run_backtest.py --symbol ETHUSDT --entry pivot \\
      --start 2024-01-01 --no-funding --set use_trailing=true stop_mult=2.0
"""

import argparse
import json

import pandas as pd

from cryptobot.backtest import run_backtest
from cryptobot.backtest.report import experiment_report
from cryptobot.config import load_backtest_config, load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.strategy import ema_rsi_signals, load_strategy_params, pivot_breakout_signals


def parse_override(text: str) -> tuple[str, object]:
    key, raw = text.split("=", 1)
    try:
        return key, json.loads(raw.lower() if raw.lower() in ("true", "false") else raw)
    except json.JSONDecodeError:
        return key, raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--name", default="manual")
    parser.add_argument("--entry", choices=["ema_rsi", "pivot"], default="ema_rsi")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--no-funding", action="store_true")
    parser.add_argument(
        "--set", nargs="*", default=[], metavar="CHAVE=VALOR",
        help="overrides de parâmetros da estratégia (ex.: stop_mult=2.0)",
    )
    args = parser.parse_args()

    data_cfg = load_data_config()
    bt_cfg = load_backtest_config()
    overrides = dict(parse_override(item) for item in args.set)
    params = load_strategy_params().model_copy(update=overrides)

    candles = pd.read_parquet(kline_path(data_cfg.data_dir, args.symbol))
    funding = None
    if not args.no_funding:
        funding = pd.read_parquet(funding_path(data_cfg.data_dir, args.symbol))["funding_rate"]

    signal_fn = ema_rsi_signals if args.entry == "ema_rsi" else pivot_breakout_signals
    signals = signal_fn(candles, params)  # indicadores aquecidos no histórico completo

    window = slice(args.start, args.end)
    result = run_backtest(
        candles.loc[window], signals.loc[window], params, bt_cfg, args.symbol, funding=funding
    )

    report_dir = experiment_report(
        result, args.name, args.symbol, params, bt_cfg,
        extra={"entry": args.entry, "funding": not args.no_funding, "overrides": overrides},
    )
    print(f"Relatório: {report_dir}")
    for chave, valor in result.summary().items():
        print(f"  {chave:15} {valor:.4f}" if isinstance(valor, float) else f"  {chave:15} {valor}")


if __name__ == "__main__":
    main()
