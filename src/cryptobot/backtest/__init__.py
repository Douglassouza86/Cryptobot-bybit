"""Motor de backtest com custos completos (taxas, funding, slippage), grid e walk-forward."""

from cryptobot.backtest.engine import REASON_LABELS, BacktestResult, run_backtest
from cryptobot.backtest.funding import funding_on_grid
from cryptobot.backtest.grid import GridSpec, expand, load_grids, plot_heatmap, run_grid
from cryptobot.backtest.report import experiment_report
from cryptobot.backtest.walkforward import split

__all__ = [
    "REASON_LABELS",
    "BacktestResult",
    "GridSpec",
    "expand",
    "experiment_report",
    "funding_on_grid",
    "load_grids",
    "plot_heatmap",
    "run_backtest",
    "run_grid",
    "split",
]
