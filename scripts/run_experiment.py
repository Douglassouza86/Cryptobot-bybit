"""T1.9-T1.12 — Protocolo experimental por hipótese (spec §5, RF-004/005/007).

Para cada (hipótese, símbolo):
  1. grid CONGELADO no IS (funding incluído) + heatmaps PF/DD;
  2. escolha MECÂNICA da configuração: argmax do score de vizinhança
     (mediana do PF nos vizinhos ±1 passo), desempate por menor DD —
     regra fixada antes de qualquer olhada no OOS;
  3. UMA ÚNICA avaliação no OOS com a configuração escolhida (sinais
     aquecidos no histórico completo, como o executor teria em produção);
  4. veredito contra o gate (PF >= 1.3 · DD <= 20% · >= 100 trades no OOS)
     + relatório padrão.

Uso: uv run python scripts/run_experiment.py [--hypothesis all] [--symbols BTCUSDT ETHUSDT]
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from cryptobot.backtest import run_backtest
from cryptobot.backtest.grid import (
    load_grids,
    neighborhood_score,
    params_from_axes,
    plot_heatmap,
    run_grid,
    signal_function,
)
from cryptobot.backtest.report import experiment_report
from cryptobot.backtest.walkforward import split
from cryptobot.config import load_backtest_config, load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.strategy import load_strategy_params

HEATMAP_AXES = {
    "h1_baseline": ("stop_mult", "tp_mult"),
    "h2_trailing": ("trail_trigger", "trail_offset"),
    "h3_pivot_breakout": ("piv_len", "stop_mult"),
    "h4_mtf_filters": ("htf_ema_len", "mtf"),
}
GATE = {"pf_min": 1.3, "dd_max": 0.20, "trades_min": 100}


def run_one(hypothesis: str, symbol: str, data_cfg, bt_cfg, base) -> dict:
    spec = load_grids()[hypothesis]
    candles = pd.read_parquet(kline_path(data_cfg.data_dir, symbol))
    funding = pd.read_parquet(funding_path(data_cfg.data_dir, symbol))["funding_rate"]
    candles_is, candles_oos = split(candles, bt_cfg.walkforward)

    print(f"\n=== {hypothesis} · {symbol} ===")
    print(f"IS  {candles_is.index[0]:%Y-%m-%d} -> {candles_is.index[-1]:%Y-%m-%d} "
          f"({len(candles_is)} candles) · grid {spec.size}")
    print(f"OOS {candles_oos.index[0]:%Y-%m-%d} -> {candles_oos.index[-1]:%Y-%m-%d} "
          f"({len(candles_oos)} candles)")

    # 1) grid no IS
    results = run_grid(candles_is, spec, base, bt_cfg, symbol, funding=funding)
    axes = list(spec.grid)
    results["pf_nbhd"] = neighborhood_score(results, axes, "pf")

    # 2) escolha mecânica
    ordenado = results.sort_values(["pf_nbhd", "dd"], ascending=[False, True])
    best = ordenado.iloc[0]
    axis_values = {a: best[a] for a in axes}
    chosen = params_from_axes(spec, base, axis_values)
    print(f"Escolhida (argmax pf_nbhd): {axis_values}")
    print(f"  IS: PF={best['pf']:.3f} (vizinhança {best['pf_nbhd']:.3f}) "
          f"DD={best['dd']:.1%} trades={int(best['trades'])}")

    # 3) OOS — uma única vez, sinais aquecidos no histórico completo
    signals = signal_function(spec.name)(candles, chosen)
    oos = run_backtest(
        candles_oos, signals.loc[candles_oos.index], chosen, bt_cfg, symbol, funding=funding
    )

    # 4) artefatos + veredito
    stamp = datetime.now(timezone.utc)
    out = Path("reports") / f"{stamp:%Y-%m-%d}-exp-{hypothesis}-{symbol}"
    out.mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "is_results.csv", index=False)
    x, y = HEATMAP_AXES[hypothesis]
    plot_heatmap(results, x, y, "pf", out / "heatmap_pf.png")
    plot_heatmap(results, x, y, "dd", out / "heatmap_dd.png")
    experiment_report(
        oos, f"oos-{hypothesis}-{symbol}", symbol, chosen, bt_cfg, out_dir=out,
        extra={"hypothesis": hypothesis, "window": "oos", "chosen_axes": axis_values},
    )

    aprovado = (
        oos.profit_factor >= GATE["pf_min"]
        and oos.max_drawdown <= GATE["dd_max"]
        and oos.n_trades >= GATE["trades_min"]
    )
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"

    verdict = {
        "hypothesis": hypothesis,
        "symbol": symbol,
        "chosen_axes": {k: (v.item() if hasattr(v, "item") else v) for k, v in axis_values.items()},
        "is_metrics": {
            "pf": float(best["pf"]), "pf_nbhd": float(best["pf_nbhd"]),
            "dd": float(best["dd"]), "trades": int(best["trades"]),
        },
        "oos_metrics": oos.summary(),
        "gate": dict(GATE, aprovado=aprovado),
        "git_commit": commit,
        "generated_at": stamp.isoformat(),
    }
    (out / "verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"OOS: PF={oos.profit_factor:.3f} DD={oos.max_drawdown:.1%} "
          f"trades={oos.n_trades} sharpe={oos.sharpe:.2f}")
    print(f"GATE: {'APROVADO' if aprovado else 'REPROVADO'} · artefatos em {out}")
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hypothesis", default="all", choices=["all", *HEATMAP_AXES])
    parser.add_argument("--symbols", nargs="*", default=["BTCUSDT", "ETHUSDT"])
    args = parser.parse_args()

    data_cfg = load_data_config()
    bt_cfg = load_backtest_config()
    base = load_strategy_params()
    hipoteses = list(HEATMAP_AXES) if args.hypothesis == "all" else [args.hypothesis]

    verdicts = [
        run_one(h, s, data_cfg, bt_cfg, base) for h in hipoteses for s in args.symbols
    ]

    print("\n================ RESUMO ================")
    print(f"{'hipótese':22} {'símbolo':9} {'PF OOS':>7} {'DD OOS':>7} {'trades':>7} {'gate':>9}")
    for v in verdicts:
        m = v["oos_metrics"]
        status = "APROVADO" if v["gate"]["aprovado"] else "reprovado"
        print(f"{v['hypothesis']:22} {v['symbol']:9} {m['profit_factor']:7.3f} "
              f"{m['max_drawdown']:7.1%} {m['n_trades']:7d} {status:>9}")


if __name__ == "__main__":
    main()
