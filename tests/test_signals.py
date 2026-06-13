"""T1.3 — Núcleo de sinal: testes sintéticos por regra + anti-look-ahead.

A checagem anti-look-ahead é o VERIFY central: o sinal em `t` calculado sobre
a série truncada em `t` deve ser idêntico ao calculado sobre a série completa.
"""

import numpy as np
import pandas as pd
import pytest

from cryptobot.strategy import (
    EmaRsiV2Params,
    crossover,
    crossunder,
    ema_rsi_signals,
    htf_trend,
    load_strategy_params,
    local_trend,
    pivot_breakout_signals,
    volume_ok,
)


@pytest.fixture(scope="module")
def candles() -> pd.DataFrame:
    """Random walk OHLCV reprodutível: 600 candles 1h (25 dias)."""
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=600, freq="h", tz="UTC")
    close = pd.Series(20_000 * np.exp(np.cumsum(rng.normal(0, 0.01, 600))), index=idx)
    spread = close * rng.uniform(0.001, 0.01, 600)
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "open": open_,
            "high": pd.concat([open_, close], axis=1).max(axis=1) + spread,
            "low": pd.concat([open_, close], axis=1).min(axis=1) - spread,
            "close": close,
            "volume": pd.Series(rng.uniform(10, 1000, 600), index=idx),
        }
    )


# Parâmetros curtos para gerar sinais suficientes em 600 barras
PARAMS_CURTOS = dict(
    ema_fast=10, ema_slow=30, rsi_len=7, atr_len=7, htf_ema_len=3, vol_ma_len=10
)


# ------------------------- crossover / crossunder -------------------------


def test_crossover_semantica_pine():
    serie = pd.Series([40.0, 45.0, 50.0, 44.0, 45.0, 46.0, 50.0])
    out = crossover(serie, 45.0)
    # t=2: 50 > 45 e 45 <= 45 -> True (igualdade na barra anterior conta)
    # t=5: 46 > 45 e 45 <= 45 -> True ; t=6: anterior já acima -> False
    assert out.tolist() == [False, False, True, False, False, True, False]


def test_crossunder_semantica_pine():
    serie = pd.Series([60.0, 55.0, 50.0, 56.0, 55.0, 54.0])
    out = crossunder(serie, 55.0)
    assert out.tolist() == [False, False, True, False, False, True]


def test_cross_com_nan_e_false():
    serie = pd.Series([np.nan, 50.0, 40.0])
    assert not crossover(serie, 45.0).iloc[1]  # anterior NaN -> False
    assert not crossunder(serie, 45.0).iloc[0]


def test_crossover_com_nivel_em_serie():
    """H3: ambas as comparações usam o nível vigente em t (spec §5)."""
    close = pd.Series([95.0, 99.0, 102.0, 103.0])
    nivel = pd.Series([np.nan, np.nan, 100.0, 100.0])  # nível nasce em t=2
    out = crossover(close, nivel)
    # t=2: 102 > 100 e 99 <= 100 -> True (nível recém-nascido conta)
    assert out.tolist() == [False, False, True, False]


# ------------------------------ tendências --------------------------------


def test_local_trend_sintetico():
    subida = pd.Series(np.linspace(100, 200, 120))
    up, down = local_trend(subida, 5, 20)
    assert up.iloc[-1] and not down.iloc[-1]
    up2, down2 = local_trend(subida[::-1].reset_index(drop=True), 5, 20)
    assert down2.iloc[-1] and not up2.iloc[-1]
    assert not (up & down).any()


def _candles_diarios(closes_por_dia: list[float]) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=24 * len(closes_por_dia), freq="h", tz="UTC")
    return pd.Series(np.repeat(closes_por_dia, 24), index=idx, dtype=float)


def test_htf_trend_diario_lag1():
    # closes diários [10, 20, 5, 30], ema_len=2 -> sinais por candle: 0, +1, -1, +1
    close = _candles_diarios([10.0, 20.0, 5.0, 30.0])
    trend = htf_trend(close, "D", ema_len=2, lag=1)
    por_dia = trend.groupby(trend.index.date).unique()
    # dia d usa o candle d-1 (último fechado): dia0 -> nada (0), dia1 -> 0,
    # dia2 -> +1, dia3 -> -1
    assert [v.tolist() for v in por_dia] == [[0.0], [0.0], [1.0], [-1.0]]


def test_htf_trend_diario_lag2_replica_tv():
    close = _candles_diarios([10.0, 20.0, 5.0, 30.0])
    trend = htf_trend(close, "D", ema_len=2, lag=2)
    por_dia = trend.groupby(trend.index.date).unique()
    # lag=2: dia d usa o candle d-2 -> dia2 usa d0 (0), dia3 usa d1 (+1)
    assert [v.tolist() for v in por_dia] == [[0.0], [0.0], [0.0], [1.0]]


def test_htf_trend_semanal_fronteira_segunda():
    # 3 semanas começando na segunda 2024-01-01; closes semanais [10, 20, 5]
    idx = pd.date_range("2024-01-01", periods=24 * 21, freq="h", tz="UTC")
    close = pd.Series(np.repeat([10.0, 20.0, 5.0], 24 * 7), index=idx)
    trend = htf_trend(close, "W", ema_len=2, lag=1)
    # semana 2 (a partir de seg 15/01 00:00) usa a semana 1 (+1);
    # último candle da semana 1 (dom 23:00) ainda usa a semana 0 (0)
    assert trend[pd.Timestamp("2024-01-14 23:00", tz="UTC")] == 0.0
    assert trend[pd.Timestamp("2024-01-15 00:00", tz="UTC")] == 1.0
    assert (trend[idx < pd.Timestamp("2024-01-15", tz="UTC")] == 0.0).all()


def test_htf_timeframe_invalido():
    close = _candles_diarios([10.0, 20.0])
    with pytest.raises(ValueError, match="timeframe"):
        htf_trend(close, "M", ema_len=2)


# ------------------------------- volume -----------------------------------


def test_volume_ok():
    vol = pd.Series([100.0] * 10 + [200.0, 90.0])
    out = volume_ok(vol, ma_len=10, mult=1.2)
    assert not out.iloc[:10].any()  # warm-up + 100 <= 120
    assert out.iloc[10] and not out.iloc[11]


# --------------------------- parâmetros (YAML) -----------------------------


def test_yaml_defaults_iguais_ao_modelo():
    """Garante que config/strategies/ema_rsi_v2.yaml e o modelo não divergem."""
    assert load_strategy_params() == EmaRsiV2Params()


def test_validador_ema_fast_menor_que_slow():
    with pytest.raises(ValueError, match="ema_fast"):
        EmaRsiV2Params(ema_fast=200, ema_slow=50)


# --------------------------- sinais EMA+RSI -------------------------------


def test_ema_rsi_wiring_sem_filtros(candles):
    """Sem filtros, entradas == tendência local + cruzamento de RSI + ATR válido."""
    from cryptobot.indicators import atr as atr_f
    from cryptobot.indicators import rsi as rsi_f

    p = EmaRsiV2Params(
        **PARAMS_CURTOS, use_daily=False, use_weekly=False, use_vol_filter=False
    )
    out = ema_rsi_signals(candles, p)

    up, down = local_trend(candles["close"], p.ema_fast, p.ema_slow)
    r = rsi_f(candles["close"], p.rsi_len)
    valid = atr_f(candles["high"], candles["low"], candles["close"], p.atr_len).notna()
    pd.testing.assert_series_equal(
        out["long_entry"], up & crossover(r, p.rsi_long_lvl) & valid, check_names=False
    )
    pd.testing.assert_series_equal(
        out["short_entry"], down & crossunder(r, p.rsi_short_lvl) & valid, check_names=False
    )
    assert out["long_entry"].any() or out["short_entry"].any()


def test_filtros_so_removem_entradas(candles):
    sem = ema_rsi_signals(
        candles,
        EmaRsiV2Params(**PARAMS_CURTOS, use_daily=False, use_weekly=False, use_vol_filter=False),
    )
    com = ema_rsi_signals(candles, EmaRsiV2Params(**PARAMS_CURTOS, use_daily=True))
    assert (com["long_entry"] & ~sem["long_entry"]).sum() == 0
    assert (com["short_entry"] & ~sem["short_entry"]).sum() == 0


def test_use_shorts_false_bloqueia_shorts(candles):
    p = EmaRsiV2Params(
        **PARAMS_CURTOS,
        use_daily=False,
        use_weekly=False,
        use_vol_filter=False,
        use_shorts=False,
    )
    assert not ema_rsi_signals(candles, p)["short_entry"].any()


# ------------------------- rompimento de pivôs ----------------------------


def test_pivot_breakout_cenario_completo():
    """Pivô em t=5 (100.0) confirmado em t=8; rompimento do close em t=12."""
    high = [90.0, 91, 92, 93, 94, 100, 95, 94, 93, 92, 91, 95, 103, 104, 105, 106]
    low = [88.0, 89, 90, 91, 92, 98, 93, 92, 91, 90, 89, 93, 101, 102, 103, 104]
    close = [89.0, 90, 91, 92, 93, 99, 94, 93, 92, 91, 90, 94, 102, 103, 104, 105]
    candles = pd.DataFrame(
        {"high": high, "low": low, "close": close, "volume": [100.0] * 16}
    )
    p = EmaRsiV2Params(piv_len=3, atr_len=2, trend_filter=False)
    out = pivot_breakout_signals(candles, p)

    assert out["long_entry"].sum() == 1
    assert out.index[out["long_entry"]][0] == 12  # nunca antes da confirmação (t=8)
    assert not out["short_entry"].any()  # close jamais cruza o suporte (89)


def test_pivot_trend_filter_so_remove(candles):
    base = dict(piv_len=5, atr_len=7, ema_fast=10, ema_slow=30)
    sem = pivot_breakout_signals(candles, EmaRsiV2Params(**base, trend_filter=False))
    com = pivot_breakout_signals(candles, EmaRsiV2Params(**base, trend_filter=True))
    assert (com["long_entry"] & ~sem["long_entry"]).sum() == 0
    assert (com["short_entry"] & ~sem["short_entry"]).sum() == 0


# ----------------------------- anti-look-ahead -----------------------------


@pytest.mark.parametrize(
    "make_params, signal_fn",
    [
        (
            lambda: EmaRsiV2Params(**PARAMS_CURTOS, use_daily=True, use_vol_filter=True),
            ema_rsi_signals,
        ),
        (
            lambda: EmaRsiV2Params(
                **PARAMS_CURTOS, piv_len=5, trend_filter=True
            ),
            pivot_breakout_signals,
        ),
    ],
    ids=["ema_rsi", "pivot_breakout"],
)
def test_anti_look_ahead(candles, make_params, signal_fn):
    """Sinal em t sobre a série truncada em t == sinal em t sobre a série
    completa (nenhuma regra enxerga o futuro)."""
    params = make_params()
    completo = signal_fn(candles, params)
    for t in range(100, len(candles), 25):
        truncado = signal_fn(candles.iloc[: t + 1], params).iloc[-1]
        assert truncado["long_entry"] == completo["long_entry"].iloc[t], f"look-ahead em t={t}"
        assert truncado["short_entry"] == completo["short_entry"].iloc[t], f"look-ahead em t={t}"
        np.testing.assert_allclose(truncado["atr"], completo["atr"].iloc[t], atol=1e-10)
