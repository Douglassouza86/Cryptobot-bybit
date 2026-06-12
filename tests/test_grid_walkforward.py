"""T1.7/T1.8 — Grid congelado, heatmap e split walk-forward."""

import numpy as np
import pandas as pd
import pytest

from cryptobot.backtest import (
    GridSpec,
    expand,
    load_grids,
    plot_heatmap,
    run_backtest,
    run_grid,
    split,
)
from cryptobot.backtest.grid import heatmap_table
from cryptobot.config import BacktestConfig, WalkforwardWindows, load_backtest_config
from cryptobot.strategy import EmaRsiV2Params

PARAMS_CURTOS = dict(
    ema_fast=10, ema_slow=30, rsi_len=7, atr_len=7,
    use_daily=False, use_weekly=False, use_vol_filter=False,
)
CONFIG = BacktestConfig(initial_capital=10_000.0, tick_size={"X": 0.1})


@pytest.fixture(scope="module")
def candles() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    n = 1500
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(20_000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx)
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


# --------------------------- grids congelados (YAML) ------------------------


def test_grids_congelados_tamanhos_da_spec():
    grids = load_grids()
    assert set(grids) == {"h1_baseline", "h2_trailing", "h3_pivot_breakout", "h4_mtf_filters"}
    # tamanhos congelados na spec §6
    assert grids["h1_baseline"].size == 243
    assert grids["h2_trailing"].size == 27
    assert grids["h3_pivot_breakout"].size == 54
    assert grids["h4_mtf_filters"].size == 18


def test_expand_deriva_rsi_short_e_overrides():
    combos = expand(load_grids()["h1_baseline"], EmaRsiV2Params())
    assert len(combos) == 243
    for axes, params in combos:
        assert params.rsi_short_lvl == 100 - axes["rsi_long_lvl"]
        assert not params.use_daily and not params.use_weekly and not params.use_vol_filter
        assert params.ema_fast < params.ema_slow


def test_expand_mapeia_mtf_e_volume():
    combos = expand(load_grids()["h4_mtf_filters"], EmaRsiV2Params())
    vistos = set()
    for axes, params in combos:
        vistos.add((axes["mtf"], axes["vol_filter"]))
        assert params.use_daily == ("daily" in axes["mtf"])
        assert params.use_weekly == ("weekly" in axes["mtf"])
        assert params.use_vol_filter == axes["vol_filter"]
    assert ("daily+weekly", True) in vistos and ("weekly", False) in vistos


# --------------------------------- run_grid ---------------------------------


SPEC_MINI = GridSpec(
    name="mini",
    overrides=dict(PARAMS_CURTOS),
    grid={"stop_mult": [1.0, 2.0], "tp_mult": [1.5, 2.5]},
)


def test_run_grid_bate_com_backtest_individual(candles):
    results = run_grid(candles, SPEC_MINI, EmaRsiV2Params(), CONFIG, "X")
    assert len(results) == 4
    assert {"stop_mult", "tp_mult", "pf", "dd", "trades", "sharpe"} <= set(results.columns)

    # uma célula conferida contra o caminho individual completo
    from cryptobot.strategy import ema_rsi_signals

    params = EmaRsiV2Params(**PARAMS_CURTOS, stop_mult=2.0, tp_mult=1.5)
    direto = run_backtest(candles, ema_rsi_signals(candles, params), params, CONFIG, "X")
    linha = results.query("stop_mult == 2.0 and tp_mult == 1.5").iloc[0]
    assert linha["trades"] == direto.n_trades
    np.testing.assert_allclose(linha["pf"], direto.profit_factor)
    np.testing.assert_allclose(linha["dd"], direto.max_drawdown)


def test_run_grid_cacheia_sinais(candles, monkeypatch):
    import cryptobot.backtest.grid as grid_mod
    from cryptobot.strategy import ema_rsi_signals as real_fn

    chamadas = []

    def contando(c, p):
        chamadas.append(1)
        return real_fn(c, p)

    monkeypatch.setattr(grid_mod, "ema_rsi_signals", contando)
    run_grid(candles, SPEC_MINI, EmaRsiV2Params(), CONFIG, "X")
    # stop/tp não afetam o sinal -> 4 combos, 1 único cálculo de sinais
    assert len(chamadas) == 1


# --------------------------------- heatmap ----------------------------------


def test_heatmap_mediana_distingue_pico_de_regiao(tmp_path):
    # região robusta em x=1 (pf ~1.4 estável); pico isolado em x=2/y=b (3.0)
    df = pd.DataFrame(
        {
            "x": [1, 1, 1, 1, 2, 2, 2, 2],
            "y": ["a", "a", "b", "b", "a", "a", "b", "b"],
            "z": [9, 9, 9, 9, 9, 9, 9, 9],  # dimensão extra agregada
            "pf": [1.4, 1.45, 1.38, 1.42, 0.6, 0.7, 3.0, 0.5],
        }
    )
    table = plot_heatmap(df, "x", "y", "pf", tmp_path / "hm.png")
    assert (tmp_path / "hm.png").stat().st_size > 1000
    np.testing.assert_allclose(table.loc["a", 1], 1.425)  # mediana da região
    np.testing.assert_allclose(table.loc["b", 2], 1.75)  # pico diluído pela mediana
    assert table.equals(heatmap_table(df, "x", "y", "pf"))


# ------------------------------- walk-forward -------------------------------


def test_split_janelas_sem_sobreposicao(candles):
    wf = WalkforwardWindows(is_end="2024-02-01", oos_start="2024-02-01")
    treino, teste = split(candles, wf)

    assert treino.index.max() < pd.Timestamp("2024-02-01", tz="UTC")  # is_end exclusivo
    assert teste.index.min() == pd.Timestamp("2024-02-01", tz="UTC")  # oos_start inclusivo
    assert len(treino) + len(teste) == len(candles)
    assert treino.index.intersection(teste.index).empty


def test_split_com_bordas_abertas(candles):
    wf = WalkforwardWindows(
        is_start="2024-01-10", is_end="2024-02-01",
        oos_start="2024-02-10", oos_end="2024-02-20",
    )
    treino, teste = split(candles, wf)
    assert treino.index.min() == pd.Timestamp("2024-01-10", tz="UTC")
    assert teste.index.max() < pd.Timestamp("2024-02-20", tz="UTC")
    # buraco proposital entre is_end e oos_start fica fora dos dois
    assert len(treino) + len(teste) < len(candles)


def test_walkforward_rejeita_sobreposicao():
    with pytest.raises(ValueError, match="oos_start"):
        WalkforwardWindows(is_end="2024-02-01", oos_start="2024-01-15")


def test_walkforward_do_yaml_congelado():
    wf = load_backtest_config().walkforward
    assert wf is not None
    assert wf.is_end == pd.Timestamp("2024-01-01", tz="UTC")
    assert wf.oos_start == pd.Timestamp("2024-01-01", tz="UTC")
    assert wf.oos_end is None
