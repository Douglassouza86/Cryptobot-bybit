"""Relatório padrão de experimento (T1.6, RF-007).

Cada experimento gera `reports/{YYYY-MM-DD}-{nome}/` com:
- metrics.json — métricas + parâmetros + config + git hash (reprodutibilidade:
  mesmo commit + mesma config + mesmos dados => números idênticos);
- equity.png  — curva de equity e drawdown;
- trades.csv  — trades individuais com custos.

`reports/` é gitignored; o que identifica o experimento é o JSON (config
completa + commit), não o diretório.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem display; só arquivos
import matplotlib.pyplot as plt  # noqa: E402

from cryptobot import __version__  # noqa: E402
from cryptobot.backtest.engine import BacktestResult  # noqa: E402
from cryptobot.config import BacktestConfig  # noqa: E402
from cryptobot.strategy.base import EmaRsiV2Params  # noqa: E402


def _git_info() -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "unknown", "dirty": True}


def _plot_equity(result: BacktestResult, title: str, path: Path) -> None:
    drawdown = result.equity / result.equity.cummax() - 1.0
    fig, (ax_eq, ax_dd) = plt.subplots(
        2, 1, figsize=(10, 6), sharex=True, height_ratios=[3, 1]
    )
    ax_eq.plot(result.equity.index, result.equity, lw=0.9)
    ax_eq.axhline(result.initial_capital, color="gray", lw=0.7, ls="--")
    ax_eq.set_ylabel("equity")
    ax_eq.set_title(title)
    ax_dd.fill_between(drawdown.index, drawdown, 0.0, color="firebrick", alpha=0.6)
    ax_dd.set_ylabel("drawdown")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def experiment_report(
    result: BacktestResult,
    name: str,
    symbol: str,
    params: EmaRsiV2Params,
    config: BacktestConfig,
    out_dir: Path = Path("reports"),
    extra: dict | None = None,
) -> Path:
    """Escreve o pacote do experimento e devolve o diretório criado."""
    stamp = datetime.now(timezone.utc)
    report_dir = out_dir / f"{stamp:%Y-%m-%d}-{name}"
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "experiment": name,
        "symbol": symbol,
        "window": {
            "start": str(result.equity.index[0]),
            "end": str(result.equity.index[-1]),
            "bars": int(len(result.equity)),
        },
        "metrics": result.summary(),
        "params": params.model_dump(),
        "backtest_config": config.model_dump(),
        "git": _git_info(),
        "cryptobot_version": __version__,
        "generated_at": stamp.isoformat(),
    }
    if extra:
        payload["extra"] = extra

    (report_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    result.trades.to_csv(report_dir / "trades.csv", index=False)
    _plot_equity(result, f"{name} — {symbol}", report_dir / "equity.png")
    return report_dir
