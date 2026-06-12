"""Motor de backtest com custos completos (taxas, funding, slippage), grid e walk-forward."""

from cryptobot.backtest.engine import REASON_LABELS, BacktestResult, run_backtest
from cryptobot.backtest.funding import funding_on_grid

__all__ = ["REASON_LABELS", "BacktestResult", "funding_on_grid", "run_backtest"]
