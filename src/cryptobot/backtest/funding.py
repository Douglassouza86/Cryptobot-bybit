"""Funding rate no backtest (T1.4, RF-003) — o vectorbt/TradingView não simulam.

Convenção (spec §2): cada evento de funding (00/08/16 UTC) é atribuído à
barra que o CONTÉM e cobrado na abertura dela, sobre posição CARREGADA da
barra anterior, ao preço de abertura. Em timeframes <= 1h o evento coincide
com a abertura da própria barra (comportamento exato); em barras diárias os
eventos de 08h/16h são SOMADOS na barra do dia e cobrados na abertura —
aproximação aceitável, usada apenas em relatórios informativos.
Long paga taxa positiva; short recebe (taxa negativa inverte sozinha).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def funding_on_grid(index: pd.DatetimeIndex, funding: pd.Series) -> pd.Series:
    """Soma das taxas de funding por barra [open_t, open_t + passo).

    Eventos fora do range das barras são ignorados; um evento dentro do
    range sempre cai em exatamente uma barra (índice contínuo — garantido
    pela integridade da Fase 0).
    """
    passo = index.to_series().diff().median()
    inicio, fim = index[0], index[-1] + passo
    eventos = funding.loc[(funding.index >= inicio) & (funding.index < fim)]

    out = np.zeros(len(index), dtype=np.float64)
    posicoes = index.searchsorted(eventos.index, side="right") - 1
    np.add.at(out, posicoes, eventos.to_numpy(dtype=np.float64))
    return pd.Series(out, index=index, name="funding_rate")
