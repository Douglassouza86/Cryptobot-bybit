"""N1 Donchian — regras, descarte de combos inválidos e anti-look-ahead."""

import numpy as np
import pandas as pd
import pytest

from cryptobot.backtest.grid import GridSpec, expand, load_grids
from cryptobot.indicators import donchian_high, donchian_low
from cryptobot.strategy import DonchianParams, donchian_signals, get_family


@pytest.fixture(scope="module")
def candles() -> pd.DataFrame:
    rng = np.random.default_rng(31)
    n = 800
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(20_000 * np.exp(np.cumsum(rng.normal(0, 0.012, n))), index=idx)
    spread = close * rng.uniform(0.001, 0.01, n)
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "open": open_,
            "high": pd.concat([open_, close], axis=1).max(axis=1) + spread,
            "low": pd.concat([open_, close], axis=1).min(axis=1) - spread,
            "close": close,
            "volume": pd.Series(rng.uniform(10, 1000, n), index=idx),
        }
    )


def test_params_valida_exit_menor_que_entry():
    with pytest.raises(ValueError, match="exit_len"):
        DonchianParams(entry_len=20, exit_len=20)
    DonchianParams(entry_len=20, exit_len=10)  # ok


def test_breakout_regra_basica():
    """Rompimento confirmado quando close supera o topo do canal anterior."""
    # canal sobe até 110; close em t=6 (115) rompe o topo dos 5 anteriores
    high = [100, 101, 102, 103, 104, 110, 115, 112, 111, 109, 108, 100]
    low = [90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 97, 90]
    close = [99, 100, 101, 102, 103, 109, 115, 111, 110, 108, 100, 95]
    candles = pd.DataFrame(
        {"high": high, "low": low, "close": close, "volume": [100.0] * 12}
    )
    p = DonchianParams(entry_len=5, exit_len=2, atr_len=3, daily_filter=False)
    sig = donchian_signals(candles, p)

    # entry_upper[t] = highest(high,5)[t-1]; em t=6 -> max(high[1..5])=110, close=115>110
    assert sig["long_entry"].iloc[6]
    # consistência: nenhuma entrada antes do warm-up (entry_len + atr)
    assert not sig["long_entry"].iloc[:5].any()


def test_daily_filter_so_remove(candles):
    sem = donchian_signals(candles, DonchianParams(entry_len=20, exit_len=10, daily_filter=False))
    com = donchian_signals(candles, DonchianParams(entry_len=20, exit_len=10, daily_filter=True))
    assert (com["long_entry"] & ~sem["long_entry"]).sum() == 0
    assert (com["short_entry"] & ~sem["short_entry"]).sum() == 0
    assert sem["long_entry"].any()  # há rompimentos no fixture


def test_use_shorts_false(candles):
    p = DonchianParams(entry_len=20, exit_len=10, daily_filter=False, use_shorts=False)
    assert not donchian_signals(candles, p)["short_entry"].any()


def test_contrato_de_colunas(candles):
    sig = donchian_signals(candles, DonchianParams(daily_filter=False))
    assert {"long_entry", "short_entry", "long_exit", "short_exit", "atr"} <= set(sig.columns)
    assert sig["long_entry"].dtype == bool and sig["long_exit"].dtype == bool


def test_grid_descarta_exit_maior_igual_entry():
    spec = load_grids(get_family("donchian").yaml_path)["n1_donchian"]
    assert spec.size == 36  # produto bruto
    combos = expand(spec, DonchianParams())
    assert len(combos) == 30  # 6 combos (entry=20, exit=20) descartados
    for _, params in combos:
        assert params.exit_len < params.entry_len


def test_expand_invalido_em_familia_v2_nao_quebra():
    """Grid com ema_fast >= ema_slow em todas as combos -> lista vazia, sem erro."""
    from cryptobot.strategy import EmaRsiV2Params

    spec = GridSpec(name="x", overrides={}, grid={"ema_fast": [200], "ema_slow": [50]})
    assert expand(spec, EmaRsiV2Params()) == []


# ----------------------------- anti-look-ahead -----------------------------


@pytest.mark.parametrize("daily_filter", [False, True])
def test_anti_look_ahead(candles, daily_filter):
    params = DonchianParams(entry_len=20, exit_len=10, atr_len=14, daily_filter=daily_filter)
    completo = donchian_signals(candles, params)
    for t in range(120, len(candles), 30):
        truncado = donchian_signals(candles.iloc[: t + 1], params).iloc[-1]
        for col in ("long_entry", "short_entry", "long_exit", "short_exit"):
            assert truncado[col] == completo[col].iloc[t], f"look-ahead em {col} t={t}"
        np.testing.assert_allclose(truncado["atr"], completo["atr"].iloc[t], atol=1e-10)


def test_donchian_indicador_nao_olha_futuro(candles):
    """donchian_high/low até t batem com o cálculo sobre a série truncada."""
    full_h = donchian_high(candles["high"], 20)
    full_l = donchian_low(candles["low"], 20)
    for t in (100, 300, 500):
        np.testing.assert_allclose(
            donchian_high(candles["high"].iloc[: t + 1], 20).iloc[-1], full_h.iloc[t]
        )
        np.testing.assert_allclose(
            donchian_low(candles["low"].iloc[: t + 1], 20).iloc[-1], full_l.iloc[t]
        )
