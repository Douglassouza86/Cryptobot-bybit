"""Split walk-forward IS/OOS (T1.8, RF-005).

Protocolo (spec §5): grid e escolha de região robusta acontecem SÓ no IS;
o OOS é avaliado UMA única vez por hipótese, com a configuração já escolhida.
As janelas vêm congeladas de config/backtest.yaml (WalkforwardWindows
garante, por validação, que não há sobreposição).
"""

from __future__ import annotations

import pandas as pd

from cryptobot.config import WalkforwardWindows


def split(frame: pd.DataFrame, wf: WalkforwardWindows) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide um frame indexado por tempo em (IS, OOS).

    IS = [is_start, is_end) · OOS = [oos_start, oos_end); None = borda dos dados.
    """
    idx = frame.index

    is_mask = idx < wf.is_end
    if wf.is_start is not None:
        is_mask &= idx >= wf.is_start

    oos_mask = idx >= wf.oos_start
    if wf.oos_end is not None:
        oos_mask &= idx < wf.oos_end

    return frame.loc[is_mask], frame.loc[oos_mask]
