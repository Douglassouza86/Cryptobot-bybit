"""T1.4 — Motor de backtest: cenários calculados à mão (VERIFY do gate).

Capital 10000, taker 0.055%, tick 0.1, slippage 2 ticks (0.2), risco 1%,
ATR fixo em 100 -> stop_dist 150, tp_dist 250, qty inicial = 100/150 = 2/3.
"""

import numpy as np
import pandas as pd
import pytest

from cryptobot.backtest import BacktestResult, funding_on_grid, run_backtest
from cryptobot.config import BacktestConfig
from cryptobot.strategy import EmaRsiV2Params

CONFIG = BacktestConfig(
    initial_capital=10_000.0,
    taker_fee_pct=0.055,
    slippage_ticks=2,
    tick_size={"TEST": 0.1},
)
FEE = 0.00055
SLIP = 0.2
ATR = 100.0
QTY0 = 10_000.0 * 0.01 / 150.0  # 2/3


def make_candles(rows: list[tuple], start: str = "2024-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(rows), freq="h", tz="UTC")
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    frame["volume"] = 100.0
    return frame


def make_signals(index: pd.Index, long_at: tuple = (), short_at: tuple = ()) -> pd.DataFrame:
    sig = pd.DataFrame(
        {"long_entry": False, "short_entry": False, "atr": ATR}, index=index
    )
    sig.iloc[list(long_at), sig.columns.get_loc("long_entry")] = True
    sig.iloc[list(short_at), sig.columns.get_loc("short_entry")] = True
    return sig


def run(candles, signals, funding=None, **overrides) -> BacktestResult:
    params = EmaRsiV2Params(**overrides)
    return run_backtest(candles, signals, params, CONFIG, "TEST", funding=funding)


FLAT = (50_000.0, 50_100.0, 49_950.0, 50_050.0)  # barra neutra (não toca stop/alvo)


# ------------------------------ long com alvo ------------------------------


def test_long_take_profit_com_fees_a_mao():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),  # t2: SINAL (close 50000)
            (50_000, 50_100, 49_950, 50_050),  # t3: entrada na abertura
            (50_050, 50_100, 49_900, 50_000),  # t4: dentro do range
            (50_100, 50_300, 50_050, 50_200),  # t5: high >= tp 50250 -> limit
        ]
    )
    res = run(candles, make_signals(candles.index, long_at=(2,)))

    assert res.n_trades == 1
    trade = res.trades.iloc[0]
    entry_fill = 50_000.0 + SLIP
    assert trade["reason"] == "tp"
    assert trade["side"] == "long"
    np.testing.assert_allclose(trade["entry_price"], entry_fill)
    np.testing.assert_allclose(trade["exit_price"], 50_250.0)  # limit: sem slippage
    np.testing.assert_allclose(trade["qty"], QTY0)

    # VERIFY: total de fees confere com cálculo manual
    fees_esperado = FEE * QTY0 * entry_fill + FEE * QTY0 * 50_250.0
    np.testing.assert_allclose(trade["fees"], fees_esperado)
    np.testing.assert_allclose(res.total_fees, fees_esperado)

    pnl_esperado = QTY0 * (50_250.0 - entry_fill) - fees_esperado
    np.testing.assert_allclose(trade["pnl"], pnl_esperado)
    np.testing.assert_allclose(res.equity.iloc[-1], 10_000.0 + pnl_esperado)

    # equity intermediário marcado a mercado no close
    cash_pos_entrada = 10_000.0 - FEE * QTY0 * entry_fill
    np.testing.assert_allclose(
        res.equity.iloc[3], cash_pos_entrada + QTY0 * (50_050.0 - entry_fill)
    )


def test_pior_caso_stop_e_alvo_no_mesmo_candle():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),  # t2: sinal
            (50_000, 50_100, 49_950, 50_050),  # t3: entrada
            (50_000, 50_300, 49_800, 50_000),  # t4: alvo E stop -> stop primeiro
        ]
    )
    res = run(candles, make_signals(candles.index, long_at=(2,)))
    trade = res.trades.iloc[0]
    assert trade["reason"] == "stop"
    np.testing.assert_allclose(trade["exit_price"], 49_850.0 - SLIP)


def test_gap_atraves_do_stop_preenche_na_abertura():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),
            (50_000, 50_100, 49_950, 50_050),
            (49_700, 49_750, 49_600, 49_700),  # abre abaixo do stop 49850
        ]
    )
    trade = run(candles, make_signals(candles.index, long_at=(2,))).trades.iloc[0]
    assert trade["reason"] == "stop"
    np.testing.assert_allclose(trade["exit_price"], 49_700.0 - SLIP)


def test_gap_acima_do_alvo_preenche_melhor():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),
            (50_000, 50_100, 49_950, 50_050),
            (50_400, 50_500, 50_350, 50_450),  # abre acima do alvo 50250
        ]
    )
    trade = run(candles, make_signals(candles.index, long_at=(2,))).trades.iloc[0]
    assert trade["reason"] == "tp"
    np.testing.assert_allclose(trade["exit_price"], 50_400.0)  # limit no melhor preço


# --------------------------------- short -----------------------------------


def test_short_espelhado():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),  # t2: sinal short
            (50_000, 50_050, 49_900, 49_950),  # t3: entrada (fill 49999.8)
            (50_000, 50_050, 49_700, 49_800),  # t4: low <= tp 49750
        ]
    )
    res = run(candles, make_signals(candles.index, short_at=(2,)))
    trade = res.trades.iloc[0]
    entry_fill = 50_000.0 - SLIP
    assert trade["side"] == "short"
    assert trade["reason"] == "tp"
    np.testing.assert_allclose(trade["entry_price"], entry_fill)
    np.testing.assert_allclose(trade["exit_price"], 49_750.0)
    pnl = QTY0 * (entry_fill - 49_750.0) - FEE * QTY0 * (entry_fill + 49_750.0)
    np.testing.assert_allclose(trade["pnl"], pnl)


# -------------------------------- funding ----------------------------------


def _candles_funding(n: int = 20) -> pd.DataFrame:
    # range que nunca toca stop (49850) nem alvo (50250)
    return make_candles([FLAT] * n)  # abre 00:00 -> funding em t0/t8/t16


def test_funding_a_mao_com_sinal_trocado():
    """VERIFY: funding validado à mão — long paga taxa positiva, recebe negativa."""
    candles = _candles_funding()
    funding = pd.Series(
        [0.0005, 0.0001, -0.0002],
        index=pd.to_datetime(
            ["2024-01-01 00:00", "2024-01-01 08:00", "2024-01-01 16:00"], utc=True
        ),
        name="funding_rate",
    )
    # sinal em t2, entrada em t3: o evento de t0 NÃO pode ser cobrado
    res = run(candles, make_signals(candles.index, long_at=(2,)), funding=funding)
    trade = res.trades.iloc[0]

    esperado = QTY0 * 50_000.0 * 0.0001 + QTY0 * 50_000.0 * -0.0002  # = -3.333...
    np.testing.assert_allclose(trade["funding"], esperado)
    np.testing.assert_allclose(res.total_funding, esperado)
    assert trade["reason"] == "end_of_data"
    np.testing.assert_allclose(trade["exit_price"], candles["close"].iloc[-1] - SLIP)

    # pnl líquido desconta fees e funding
    fees = FEE * QTY0 * (trade["entry_price"] + trade["exit_price"])
    pnl = QTY0 * (trade["exit_price"] - trade["entry_price"]) - fees - esperado
    np.testing.assert_allclose(trade["pnl"], pnl)


def test_funding_nao_cobra_na_barra_da_entrada():
    candles = _candles_funding()
    funding = pd.Series(
        [0.001, 0.0001],
        index=pd.to_datetime(["2024-01-01 08:00", "2024-01-01 16:00"], utc=True),
        name="funding_rate",
    )
    # sinal em t7 -> entrada em t8 (exatamente no evento das 08:00): não paga
    res = run(candles, make_signals(candles.index, long_at=(7,)), funding=funding)
    np.testing.assert_allclose(res.trades.iloc[0]["funding"], QTY0 * 50_000.0 * 0.0001)


def test_funding_on_grid_valida_grade():
    idx = pd.date_range("2024-01-01", periods=24, freq="h", tz="UTC")
    ok = pd.Series(
        [0.0001], index=pd.to_datetime(["2024-01-01 08:00"], utc=True)
    )
    aligned = funding_on_grid(idx, ok)
    assert aligned.sum() == pytest.approx(0.0001)
    assert (aligned[aligned.index.hour != 8] == 0).all()

    fora_da_grade = pd.Series(
        [0.0001], index=pd.to_datetime(["2024-01-01 08:30"], utc=True)
    )
    with pytest.raises(ValueError, match="funding"):
        funding_on_grid(idx, fora_da_grade)


# -------------------------------- trailing ---------------------------------

TRAIL = dict(use_trailing=True)  # trigger 1.5 (150), offset 2.0 (200) — defaults


def test_trailing_ativa_e_dispara_na_mesma_barra():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),  # t2: sinal (ativação = fill + 150)
            (50_000, 50_100, 49_950, 50_050),  # t3: entrada fill 50000.2
            (50_050, 50_200, 49_990, 50_000),  # t4: high>=50150.2 -> trail 50000; low<=50000
        ]
    )
    trade = run(candles, make_signals(candles.index, long_at=(2,)), **TRAIL).trades.iloc[0]
    assert trade["reason"] == "trail"
    np.testing.assert_allclose(trade["exit_price"], 50_000.0 - SLIP)


def test_trailing_ratchet_so_sobe():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),
            (50_000, 50_100, 49_950, 50_050),  # entrada
            (50_050, 50_200, 50_060, 50_150),  # ativa: trail = 50200-200 = 50000
            (50_150, 50_500, 50_310, 50_400),  # trail sobe p/ 50300; low 50310 > trail
            (50_400, 50_450, 50_200, 50_250),  # cand 50250 < 50300: NÃO desce; dispara
        ]
    )
    trade = run(candles, make_signals(candles.index, long_at=(2,)), **TRAIL).trades.iloc[0]
    assert trade["reason"] == "trail"
    np.testing.assert_allclose(trade["exit_price"], 50_300.0 - SLIP)  # não 50250


def test_trailing_stop_fixo_continua_ativo():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),
            (50_000, 50_100, 49_950, 50_050),
            (50_000, 50_100, 49_800, 49_900),  # low <= stop 49850 antes de ativar
        ]
    )
    trade = run(candles, make_signals(candles.index, long_at=(2,)), **TRAIL).trades.iloc[0]
    assert trade["reason"] == "stop"
    np.testing.assert_allclose(trade["exit_price"], 49_850.0 - SLIP)


# --------------------------- posição e compounding -------------------------


def test_sem_piramidacao_e_reentrada_com_compounding():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),  # t2: sinal 1
            (50_000, 50_100, 49_950, 50_050),  # t3: entrada 1
            (50_050, 50_100, 49_950, 50_000),  # t4: sinal extra IGNORADO (posição aberta)
            (50_100, 50_300, 50_050, 50_200),  # t5: tp do trade 1; sinal 2 no close
            (50_200, 50_250, 50_150, 50_200),  # t6: entrada 2
            FLAT,
        ]
    )
    res = run(candles, make_signals(candles.index, long_at=(2, 4, 5)))
    assert res.n_trades == 2

    # qty do trade 2 usa o caixa APÓS o trade 1 (sizing compõe sobre o equity)
    t1, t2 = res.trades.iloc[0], res.trades.iloc[1]
    assert t1["reason"] == "tp"
    cash_apos_t1 = 10_000.0 + t1["pnl"]
    np.testing.assert_allclose(t2["qty"], cash_apos_t1 * 0.01 / 150.0)
    np.testing.assert_allclose(t2["entry_price"], 50_200.0 + SLIP)


def test_metricas_basicas():
    candles = make_candles(
        [
            FLAT,
            FLAT,
            (50_000, 50_050, 49_950, 50_000),
            (50_000, 50_100, 49_950, 50_050),
            (50_100, 50_300, 50_050, 50_200),  # tp -> trade vencedor
        ]
    )
    res = run(candles, make_signals(candles.index, long_at=(2,)))
    assert res.win_rate == 1.0
    assert res.profit_factor == float("inf")  # sem perdas
    assert 0.0 <= res.max_drawdown < 0.01
    assert res.total_return == pytest.approx(res.trades["pnl"].sum() / 10_000.0)


# ----------------------------- dados reais (smoke) --------------------------


def test_smoke_dados_reais_btc():
    """Roda o pipeline completo numa janela real (skip sem cache)."""
    from cryptobot.config import load_data_config
    from cryptobot.data.downloader import funding_path, kline_path
    from cryptobot.strategy import ema_rsi_signals, load_strategy_params

    cfg = load_data_config()
    kpath = kline_path(cfg.data_dir, "BTCUSDT")
    fpath = funding_path(cfg.data_dir, "BTCUSDT")
    if not kpath.exists() or not fpath.exists():
        pytest.skip("cache de dados ausente (rode scripts/download_data.py)")

    candles = pd.read_parquet(kpath).loc["2024":]
    funding = pd.read_parquet(fpath)["funding_rate"]
    signals = ema_rsi_signals(candles, load_strategy_params())
    res = run_backtest(
        candles,
        signals,
        load_strategy_params(),
        BacktestConfig(tick_size={"BTCUSDT": 0.1}),
        "BTCUSDT",
        funding=funding,
    )
    assert np.isfinite(res.equity).all()
    assert res.n_trades > 0
    assert set(res.trades["reason"]) <= {"stop", "tp", "trail", "end_of_data"}
    assert res.total_funding != 0.0  # funding de fato aplicado
