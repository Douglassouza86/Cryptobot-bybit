"""Grid de parâmetros + heatmap PF/DD (T1.7, RF-004).

Os grids vêm CONGELADOS de config/strategies/ema_rsi_v2.yaml (spec §6).
Eixos especiais do YAML são traduzidos para parâmetros:
- rsi_long_lvl  -> rsi_short_lvl = 100 - rsi_long_lvl (regra de simetria);
- mtf           -> use_daily/use_weekly ("daily", "weekly", "daily+weekly");
- vol_filter    -> use_vol_filter (ma_len/mult ficam nos defaults).

Sinais são cacheados por combinação de parâmetros que afetam o sinal
(stop/alvo/trailing/risco só afetam o motor), então um grid 243 só
recalcula sinais ~27 vezes.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ValidationError

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cryptobot.backtest.engine import run_backtest  # noqa: E402
from cryptobot.config import BacktestConfig  # noqa: E402
from cryptobot.strategy import (  # noqa: E402
    ema_rsi_signals,
    pivot_breakout_signals,
)
from cryptobot.strategy.base import DEFAULT_PARAMS_PATH  # noqa: E402

# parâmetros que alteram o SINAL (o restante só altera a execução no motor);
# união de todas as famílias de estratégia — campos ausentes viram None
SIGNAL_FIELDS = (
    "ema_fast", "ema_slow", "rsi_len", "rsi_long_lvl", "rsi_short_lvl",
    "use_daily", "use_weekly", "htf_ema_len", "htf_lag",
    "use_vol_filter", "vol_ma_len", "vol_mult", "atr_len", "use_shorts",
    "piv_len", "trend_filter",
    "entry_len", "daily_filter",  # N1 Donchian
)

_AXIS_MAPPERS = {
    "rsi_long_lvl": lambda v: {"rsi_long_lvl": v, "rsi_short_lvl": 100 - v},
    "mtf": lambda v: {"use_daily": "daily" in v, "use_weekly": "weekly" in v},
    "vol_filter": lambda v: {"use_vol_filter": bool(v)},
}

METRIC_COLUMNS = ["pf", "dd", "trades", "sharpe", "win_rate", "total_return"]


@dataclass(frozen=True)
class GridSpec:
    name: str
    overrides: dict
    grid: dict[str, list]

    @property
    def size(self) -> int:
        out = 1
        for valores in self.grid.values():
            out *= len(valores)
        return out


def load_grids(path: Path = DEFAULT_PARAMS_PATH) -> dict[str, GridSpec]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        nome: GridSpec(name=nome, overrides=item.get("overrides", {}), grid=item["grid"])
        for nome, item in raw["grids"].items()
    }


def params_from_axes(spec: GridSpec, base: BaseModel, axis_values: dict) -> BaseModel:
    """Aplica overrides da hipótese + valores dos eixos (com mapeamento) à base.

    Reconstrói via model_validate para REVALIDAR (model_copy não dispara os
    validadores), permitindo que expand descarte combinações inválidas.
    """
    updates = dict(spec.overrides)
    for eixo, valor in axis_values.items():
        mapper = _AXIS_MAPPERS.get(eixo)
        updates.update(mapper(valor) if mapper else {eixo: valor})
    return type(base).model_validate({**base.model_dump(), **updates})


def expand(spec: GridSpec, base: BaseModel) -> list[tuple[dict, BaseModel]]:
    """Produto cartesiano do grid -> [(valores_dos_eixos, params_completos)].

    Combinações que violam os validadores da família (ex.: exit_len >=
    entry_len na Donchian) são silenciosamente descartadas.
    """
    eixos = list(spec.grid)
    combos: list[tuple[dict, BaseModel]] = []
    for valores in itertools.product(*(spec.grid[eixo] for eixo in eixos)):
        axis_values = dict(zip(eixos, valores))
        try:
            params = params_from_axes(spec, base, axis_values)
        except (ValueError, ValidationError):
            continue
        combos.append((axis_values, params))
    return combos


def neighborhood_score(
    results: pd.DataFrame, axes: list[str], metric: str = "pf"
) -> pd.Series:
    """Mediana da métrica na vizinhança de cada combinação (regra da spec §5/§7).

    Vizinhos = combinações iguais em todos os eixos exceto no máximo UM,
    que difere em exatamente um passo na ordem do grid congelado (a própria
    combinação inclusa). Um pico isolado tem vizinhança ruim e dilui; o
    centro de uma região robusta mantém o score alto. A escolha da
    configuração para o OOS é o argmax deste score (desempate: menor DD) —
    regra mecânica, fixada ANTES de olhar o OOS.
    """
    ords = np.column_stack(
        [
            results[a].map({v: i for i, v in enumerate(pd.unique(results[a]))}).to_numpy()
            for a in axes
        ]
    )
    dist = np.abs(ords[:, None, :] - ords[None, :, :]).sum(axis=2)
    vals = results[metric].to_numpy(dtype=float)
    return pd.Series(
        [float(np.nanmedian(vals[dist[i] <= 1])) for i in range(len(results))],
        index=results.index,
        name=f"{metric}_nbhd",
    )


def signal_function(hypothesis: str):
    """Resolve a função de sinal do ciclo v2 pelo nome da hipótese (legado).

    Famílias do ciclo v3 passam `signal_fn` explicitamente para run_grid.
    """
    return pivot_breakout_signals if hypothesis == "h3_pivot_breakout" else ema_rsi_signals


def run_grid(
    candles: pd.DataFrame,
    spec: GridSpec,
    base: BaseModel,
    config: BacktestConfig,
    symbol: str,
    funding: pd.Series | None = None,
    signal_fn=None,
) -> pd.DataFrame:
    """Roda todas as combinações e devolve eixos + métricas por linha.

    `signal_fn` None usa o mapeamento legado do ciclo v2 (signal_function);
    famílias v3 passam a função explicitamente.

    IMPORTANTE: chame com candles JÁ recortados no IS (walkforward.split) —
    o grid jamais deve enxergar o OOS.
    """
    if signal_fn is None:
        signal_fn = signal_function(spec.name)
    cache: dict[tuple, pd.DataFrame] = {}
    linhas = []
    for axis_values, params in expand(spec, base):
        chave = tuple(getattr(params, campo, None) for campo in SIGNAL_FIELDS)
        if chave not in cache:
            cache[chave] = signal_fn(candles, params)
        res = run_backtest(candles, cache[chave], params, config, symbol, funding=funding)
        linhas.append(
            {
                **axis_values,
                "pf": res.profit_factor,
                "dd": res.max_drawdown,
                "trades": res.n_trades,
                "sharpe": res.sharpe,
                "win_rate": res.win_rate,
                "total_return": res.total_return,
            }
        )
    return pd.DataFrame(linhas)


def heatmap_table(
    results: pd.DataFrame, x: str, y: str, metric: str, agg: str = "median"
) -> pd.DataFrame:
    """Pivô y×x da métrica, agregando as demais dimensões (mediana por padrão).

    A mediana sobre as outras dimensões é o que separa região robusta de pico
    isolado: um pico que só existe numa combinação específica dilui; uma
    região boa sobrevive à agregação.
    """
    return results.pivot_table(index=y, columns=x, values=metric, aggfunc=agg)


def plot_heatmap(
    results: pd.DataFrame,
    x: str,
    y: str,
    metric: str,
    path: Path,
    agg: str = "median",
    title: str | None = None,
) -> pd.DataFrame:
    table = heatmap_table(results, x, y, metric, agg)
    fig, ax = plt.subplots(figsize=(1.6 + 1.1 * len(table.columns), 1.2 + 0.8 * len(table)))
    dados = table.to_numpy(dtype=float)
    im = ax.imshow(dados, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(table.columns)), [str(c) for c in table.columns])
    ax.set_yticks(range(len(table.index)), [str(i) for i in table.index])
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title(title or f"{metric} ({agg} sobre demais dimensões)")
    for i in range(dados.shape[0]):
        for j in range(dados.shape[1]):
            if np.isfinite(dados[i, j]):
                ax.text(j, i, f"{dados[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return table
