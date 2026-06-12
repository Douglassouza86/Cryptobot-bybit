"""Funding rate no backtest (T1.4, RF-003) — o vectorbt/TradingView não simulam.

Convenção (spec §2): o evento de funding das 00/08/16 UTC é cobrado na
abertura da barra 1h cujo timestamp coincide com o evento, sobre a posição
CARREGADA da barra anterior (entrada na própria abertura não paga), ao preço
de abertura da barra. Long paga taxa positiva; short recebe (sinais invertem
automaticamente com taxa negativa).
"""

from __future__ import annotations

import pandas as pd


def funding_on_grid(index: pd.DatetimeIndex, funding: pd.Series) -> pd.Series:
    """Alinha a série de funding (grade 8h) às barras 1h: taxa na barra cuja
    abertura coincide com o evento, 0.0 nas demais.

    Falha se algum evento dentro do range das barras não casar com uma
    abertura — indicaria cache corrompido (a integridade da Fase 0 garante
    a grade 00/08/16 UTC).
    """
    aligned = funding.reindex(index)
    in_range = funding.loc[(funding.index >= index[0]) & (funding.index <= index[-1])]
    matched = int(aligned.notna().sum())
    if matched != len(in_range):
        raise ValueError(
            f"{len(in_range) - matched} evento(s) de funding sem barra 1h correspondente"
        )
    return aligned.fillna(0.0)
