"""Roda o grid congelado de uma hipótese no IS e gera heatmaps (T1.7/T1.8).

Por padrão a janela é o IS do walk-forward (config/backtest.yaml) — o grid
NUNCA deve enxergar o OOS (RF-005).

Uso:
  uv run python scripts/run_grid.py --hypothesis h1_baseline --symbol BTCUSDT
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from cryptobot.backtest.grid import load_grids, plot_heatmap, run_grid
from cryptobot.backtest.walkforward import split
from cryptobot.config import load_backtest_config, load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.strategy import load_strategy_params

# eixos default dos heatmaps por hipótese (PF e DD)
HEATMAP_AXES = {
    "h1_baseline": ("stop_mult", "tp_mult"),
    "h2_trailing": ("trail_trigger", "trail_offset"),
    "h3_pivot_breakout": ("piv_len", "stop_mult"),
    "h4_mtf_filters": ("htf_ema_len", "mtf"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hypothesis", required=True, choices=list(HEATMAP_AXES))
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--no-funding", action="store_true")
    parser.add_argument("--x", default=None, help="eixo x do heatmap")
    parser.add_argument("--y", default=None, help="eixo y do heatmap")
    args = parser.parse_args()

    data_cfg = load_data_config()
    bt_cfg = load_backtest_config()
    if bt_cfg.walkforward is None:
        raise SystemExit("config/backtest.yaml sem walkforward — grid exige janela IS")

    spec = load_grids()[args.hypothesis]
    base = load_strategy_params()

    candles = pd.read_parquet(kline_path(data_cfg.data_dir, args.symbol))
    funding = None
    if not args.no_funding:
        funding = pd.read_parquet(funding_path(data_cfg.data_dir, args.symbol))["funding_rate"]

    candles_is, _ = split(candles, bt_cfg.walkforward)
    print(
        f"{args.hypothesis} · {args.symbol} · IS {candles_is.index[0]} -> "
        f"{candles_is.index[-1]} ({len(candles_is)} candles) · {spec.size} combinações"
    )

    results = run_grid(candles_is, spec, base, bt_cfg, args.symbol, funding=funding)

    stamp = datetime.now(timezone.utc)
    out = Path("reports") / f"{stamp:%Y-%m-%d}-grid-{args.hypothesis}-{args.symbol}"
    out.mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "results.csv", index=False)

    x, y = args.x or HEATMAP_AXES[args.hypothesis][0], args.y or HEATMAP_AXES[args.hypothesis][1]
    plot_heatmap(results, x, y, "pf", out / "heatmap_pf.png")
    plot_heatmap(results, x, y, "dd", out / "heatmap_dd.png")

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"
    (out / "meta.json").write_text(
        json.dumps(
            {
                "hypothesis": args.hypothesis,
                "symbol": args.symbol,
                "window": {"start": str(candles_is.index[0]), "end": str(candles_is.index[-1])},
                "combos": spec.size,
                "funding": not args.no_funding,
                "git_commit": commit,
                "generated_at": stamp.isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    top = results.sort_values("pf", ascending=False).head(10)
    print(f"\nTop 10 por PF (IS):\n{top.to_string(index=False)}")
    print(f"\nArtefatos em {out}")


if __name__ == "__main__":
    main()
