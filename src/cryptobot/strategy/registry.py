"""Registro de famílias de estratégia (ciclo v2 + v3).

Cada família amarra: classe de parâmetros (pydantic), função de sinal pura
(candles -> contrato de sinais) e o YAML com defaults + grid congelado.
grid.py e os scripts de experimento ficam agnósticos ao tipo concreto.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel

from cryptobot.strategy.base import EmaRsiV2Params
from cryptobot.strategy.donchian import DonchianParams, donchian_signals
from cryptobot.strategy.ema_rsi_v2 import ema_rsi_signals, pivot_breakout_signals


@dataclass(frozen=True)
class StrategyFamily:
    name: str
    params_cls: type[BaseModel]
    signal_fn: Callable[[pd.DataFrame, BaseModel], pd.DataFrame]
    yaml_path: Path

    def defaults(self) -> BaseModel:
        raw = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8"))
        return self.params_cls(**raw["defaults"])


_STRAT_DIR = Path("config/strategies")

FAMILIES: dict[str, StrategyFamily] = {
    # ciclo v2 (compartilham EmaRsiV2Params e o YAML ema_rsi_v2)
    "ema_rsi_v2": StrategyFamily(
        "ema_rsi_v2", EmaRsiV2Params, ema_rsi_signals, _STRAT_DIR / "ema_rsi_v2.yaml"
    ),
    "pivot_breakout": StrategyFamily(
        "pivot_breakout", EmaRsiV2Params, pivot_breakout_signals, _STRAT_DIR / "ema_rsi_v2.yaml"
    ),
    # ciclo v3
    "donchian": StrategyFamily(
        "donchian", DonchianParams, donchian_signals, _STRAT_DIR / "donchian.yaml"
    ),
}


def get_family(name: str) -> StrategyFamily:
    if name not in FAMILIES:
        raise KeyError(f"família desconhecida: {name!r} (conhecidas: {list(FAMILIES)})")
    return FAMILIES[name]
