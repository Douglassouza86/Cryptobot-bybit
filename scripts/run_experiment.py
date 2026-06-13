"""Protocolo experimental por hipótese × símbolo × timeframe (RF-004/005/007).

Para cada combinação:
  1. grid CONGELADO no IS (funding incluído) + heatmaps PF/DD;
  2. escolha MECÂNICA: argmax do score de vizinhança (mediana do PF nos
     vizinhos ±1 passo), desempate por menor DD — fixada antes de ver o OOS;
  3. UMA ÚNICA avaliação no OOS com a config escolhida (sinais aquecidos no
     histórico completo, como o executor teria em produção);
  4. veredito vs gate (PF≥1.3 · DD≤20% · ≥100 trades) + relatório padrão.

Timeframes 1h/15m/5m são elegíveis ao gate; 1d é INFORMATIVO (trades
insuficientes p/ o gate — decisão T1.13), claramente marcado.

Uso:
  uv run python scripts/run_experiment.py --family donchian
  uv run python scripts/run_experiment.py --family ema_rsi_v2 --hypothesis h1_baseline \\
      --timeframes 1h --symbols BTCUSDT
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from cryptobot.backtest import run_backtest
from cryptobot.backtest.grid import load_grids, neighborhood_score, params_from_axes, plot_heatmap, run_grid
from cryptobot.backtest.report import experiment_report
from cryptobot.backtest.walkforward import split
from cryptobot.config import load_backtest_config, load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.strategy import get_family

# timeframe legível -> intervalo da API V5 (None = reamostrado de 1h)
TF_INTERVAL = {"5m": "5", "15m": "15", "1h": "60", "1d": None}
GATE_ELIGIBLE = {"5m", "15m", "1h"}  # 1d é informativo (poucos trades)

# eixos default dos heatmaps por hipótese
HEATMAP_AXES = {
    "h1_baseline": ("stop_mult", "tp_mult"),
    "h2_trailing": ("trail_trigger", "trail_offset"),
    "h3_pivot_breakout": ("piv_len", "stop_mult"),
    "h4_mtf_filters": ("htf_ema_len", "mtf"),
    "n1_donchian": ("entry_len", "stop_mult"),
}
GATE = {"pf_min": 1.3, "dd_max": 0.20, "trades_min": 100}


def load_candles(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    """Lê o parquet do timeframe; 1d é reamostrado a partir do 1h."""
    interval = TF_INTERVAL[timeframe]
    if interval is not None:
        return pd.read_parquet(kline_path(data_dir, symbol, interval))
    hourly = pd.read_parquet(kline_path(data_dir, symbol, "60"))
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if "turnover" in hourly.columns:
        agg["turnover"] = "sum"
    return hourly.resample("1D").agg(agg).dropna()


def run_one(family, hypothesis, symbol, timeframe, data_cfg, bt_cfg) -> dict:
    spec = load_grids(family.yaml_path)[hypothesis]
    base = family.defaults()
    candles = load_candles(data_cfg.data_dir, symbol, timeframe)
    funding = pd.read_parquet(funding_path(data_cfg.data_dir, symbol))["funding_rate"]
    candles_is, candles_oos = split(candles, bt_cfg.walkforward)
    gate_ok = timeframe in GATE_ELIGIBLE

    print(f"\n=== {hypothesis} · {symbol} · {timeframe}"
          f"{'' if gate_ok else ' (INFORMATIVO)'} ===")
    print(f"IS  {candles_is.index[0]:%Y-%m-%d} -> {candles_is.index[-1]:%Y-%m-%d} "
          f"({len(candles_is)} candles)")
    print(f"OOS {candles_oos.index[0]:%Y-%m-%d} -> {candles_oos.index[-1]:%Y-%m-%d} "
          f"({len(candles_oos)} candles)")

    # 1) grid no IS
    results = run_grid(
        candles_is, spec, base, bt_cfg, symbol, funding=funding, signal_fn=family.signal_fn
    )
    axes = list(spec.grid)
    results["pf_nbhd"] = neighborhood_score(results, axes, "pf")

    # 2) escolha mecânica
    best = results.sort_values(["pf_nbhd", "dd"], ascending=[False, True]).iloc[0]
    axis_values = {a: best[a] for a in axes}
    chosen = params_from_axes(spec, base, axis_values)
    print(f"Escolhida: {axis_values}")
    print(f"  IS: PF={best['pf']:.3f} (vizinhança {best['pf_nbhd']:.3f}) "
          f"DD={best['dd']:.1%} trades={int(best['trades'])}")

    # 3) OOS — uma única vez, sinais aquecidos no histórico completo
    signals = family.signal_fn(candles, chosen)
    oos = run_backtest(
        candles_oos, signals.loc[candles_oos.index], chosen, bt_cfg, symbol, funding=funding
    )

    # 4) artefatos + veredito
    stamp = datetime.now(timezone.utc)
    out = Path("reports") / f"{stamp:%Y-%m-%d}-exp-{hypothesis}-{symbol}-{timeframe}"
    out.mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "is_results.csv", index=False)
    x, y = HEATMAP_AXES[hypothesis]
    if x in results.columns and y in results.columns:
        plot_heatmap(results, x, y, "pf", out / "heatmap_pf.png")
        plot_heatmap(results, x, y, "dd", out / "heatmap_dd.png")
    experiment_report(
        oos, f"oos-{hypothesis}-{symbol}-{timeframe}", symbol, chosen, bt_cfg, out_dir=out,
        extra={"hypothesis": hypothesis, "timeframe": timeframe, "window": "oos",
               "gate_eligible": gate_ok, "chosen_axes": axis_values},
    )

    aprovado = gate_ok and (
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
        "family": family.name, "hypothesis": hypothesis, "symbol": symbol,
        "timeframe": timeframe, "gate_eligible": gate_ok,
        "chosen_axes": {k: (v.item() if hasattr(v, "item") else v)
                        for k, v in axis_values.items()},
        "is_metrics": {"pf": float(best["pf"]), "pf_nbhd": float(best["pf_nbhd"]),
                       "dd": float(best["dd"]), "trades": int(best["trades"])},
        "oos_metrics": oos.summary(),
        "gate": dict(GATE, aprovado=aprovado),
        "git_commit": commit, "generated_at": stamp.isoformat(),
    }
    (out / "verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"OOS: PF={oos.profit_factor:.3f} DD={oos.max_drawdown:.1%} "
          f"trades={oos.n_trades} sharpe={oos.sharpe:.2f}")
    flag = ("APROVADO" if aprovado else "REPROVADO") if gate_ok else "informativo"
    print(f"GATE: {flag} · artefatos em {out}")
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--hypothesis", default="all")
    parser.add_argument("--symbols", nargs="*", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--timeframes", nargs="*", default=["1h", "15m", "5m", "1d"])
    args = parser.parse_args()

    data_cfg = load_data_config()
    bt_cfg = load_backtest_config()
    family = get_family(args.family)
    grids = load_grids(family.yaml_path)
    hipoteses = list(grids) if args.hypothesis == "all" else [args.hypothesis]

    verdicts = [
        run_one(family, h, s, tf, data_cfg, bt_cfg)
        for h in hipoteses for s in args.symbols for tf in args.timeframes
    ]

    print("\n===================== RESUMO =====================")
    print(f"{'hipótese':14} {'símbolo':9} {'TF':>4} {'PF OOS':>7} {'DD OOS':>7} "
          f"{'trades':>7} {'veredito':>11}")
    for v in verdicts:
        m = v["oos_metrics"]
        if not v["gate_eligible"]:
            status = "informativo"
        else:
            status = "APROVADO" if v["gate"]["aprovado"] else "reprovado"
        print(f"{v['hypothesis']:14} {v['symbol']:9} {v['timeframe']:>4} "
              f"{m['profit_factor']:7.3f} {m['max_drawdown']:7.1%} "
              f"{m['n_trades']:7d} {status:>11}")


if __name__ == "__main__":
    main()
