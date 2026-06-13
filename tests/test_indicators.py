"""T1.2 — Indicadores puros vs implementações de referência (tolerância 1e-8).

Oráculos: laços ingênuos transcritos diretamente das fórmulas do Pine v5
(docs/strategy-v2-spec.md §3) — caminho de código independente do vetorizado —
mais valores calculados à mão e propriedades conhecidas (RSI 100/0, ATR
constante, semântica de confirmação dos pivôs).
"""

import numpy as np
import pandas as pd
import pytest

from cryptobot.indicators import (
    atr,
    donchian_high,
    donchian_low,
    ema,
    macd,
    pivot_high,
    pivot_low,
    rma,
    rsi,
    sma,
    supertrend,
    true_range,
)

TOL = dict(rtol=0.0, atol=1e-8)


@pytest.fixture(scope="module")
def candles() -> pd.DataFrame:
    """Random walk OHLCV reprodutível (1000 candles 1h)."""
    rng = np.random.default_rng(42)
    idx = pd.date_range("2024-01-01", periods=1000, freq="h", tz="UTC")
    close = pd.Series(20_000 * np.exp(np.cumsum(rng.normal(0, 0.01, 1000))), index=idx)
    spread = close * rng.uniform(0.001, 0.01, 1000)
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "open": open_,
            "high": pd.concat([open_, close], axis=1).max(axis=1) + spread,
            "low": pd.concat([open_, close], axis=1).min(axis=1) - spread,
            "close": close,
            "volume": pd.Series(rng.uniform(10, 1000, 1000), index=idx),
        }
    )


# ----------------------- oráculos de referência -----------------------


def _ema_ref(values: np.ndarray, length: int) -> np.ndarray:
    alpha = 2.0 / (length + 1)
    out = np.empty_like(values)
    out[0] = values[0]
    for t in range(1, len(values)):
        out[t] = alpha * values[t] + (1 - alpha) * out[t - 1]
    return out


def _rma_ref(values: np.ndarray, length: int) -> np.ndarray:
    out = np.full(values.shape, np.nan)
    valid = np.where(~np.isnan(values))[0]
    first = valid[0]
    seed_idx = first + length - 1
    out[seed_idx] = values[first : seed_idx + 1].mean()
    alpha = 1.0 / length
    for t in range(seed_idx + 1, len(values)):
        out[t] = alpha * values[t] + (1 - alpha) * out[t - 1]
    return out


def _rsi_ref(close: np.ndarray, length: int) -> np.ndarray:
    delta = np.diff(close, prepend=np.nan)
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    up[0] = down[0] = np.nan
    avg_up, avg_down = _rma_ref(up, length), _rma_ref(down, length)
    return 100.0 * avg_up / (avg_up + avg_down)


def _atr_ref(h: np.ndarray, lo: np.ndarray, c: np.ndarray, length: int) -> np.ndarray:
    tr = np.empty_like(h)
    tr[0] = h[0] - lo[0]
    for t in range(1, len(h)):
        tr[t] = max(h[t] - lo[t], abs(h[t] - c[t - 1]), abs(lo[t] - c[t - 1]))
    return _rma_ref(tr, length)


# ----------------------------- EMA / SMA ------------------------------


@pytest.mark.parametrize("length", [3, 14, 50, 200])
def test_ema_vs_referencia(candles, length):
    expected = _ema_ref(candles["close"].to_numpy(), length)
    np.testing.assert_allclose(ema(candles["close"], length).to_numpy(), expected, **TOL)


def test_ema_valores_a_mao():
    # length=3 -> alpha=0.5: 1, 1.5, 2.25, 3.125, 4.0625
    out = ema(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
    np.testing.assert_allclose(out.to_numpy(), [1.0, 1.5, 2.25, 3.125, 4.0625], **TOL)


def test_sma_basico(candles):
    out = sma(candles["volume"], 20)
    assert out.iloc[:19].isna().all()
    expected = candles["volume"].iloc[:20].mean()
    np.testing.assert_allclose(out.iloc[19], expected, **TOL)


# ----------------------------- RMA / RSI ------------------------------


@pytest.mark.parametrize("length", [3, 14])
def test_rma_vs_referencia(candles, length):
    expected = _rma_ref(candles["close"].to_numpy(), length)
    np.testing.assert_allclose(rma(candles["close"], length).to_numpy(), expected, **TOL)


def test_rma_valores_a_mao():
    # length=3, semente = mean(1,2,3)=2; depois alpha=1/3:
    # rma[3] = 4/3 + 2*2/3 = 8/3 ; rma[4] = 5/3 + (8/3)*(2/3) = 31/9
    out = rma(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
    assert out.iloc[:2].isna().all()
    np.testing.assert_allclose(out.iloc[2:].to_numpy(), [2.0, 8.0 / 3.0, 31.0 / 9.0], **TOL)


def test_rma_pula_nan_iniciais():
    serie = pd.Series([np.nan, np.nan, 1.0, 2.0, 3.0, 4.0])
    out = rma(serie, 3)
    assert out.iloc[:4].isna().all()
    np.testing.assert_allclose(out.iloc[4], 2.0, **TOL)  # mean(1,2,3)
    np.testing.assert_allclose(out.iloc[5], 8.0 / 3.0, **TOL)


@pytest.mark.parametrize("length", [7, 14])
def test_rsi_vs_referencia(candles, length):
    expected = _rsi_ref(candles["close"].to_numpy(), length)
    np.testing.assert_allclose(rsi(candles["close"], length).to_numpy(), expected, **TOL)


def test_rsi_extremos():
    subida = pd.Series(np.arange(1.0, 31.0))  # só altas -> 100
    descida = pd.Series(np.arange(31.0, 1.0, -1.0))  # só baixas -> 0
    np.testing.assert_allclose(rsi(subida, 14).iloc[-1], 100.0, **TOL)
    np.testing.assert_allclose(rsi(descida, 14).iloc[-1], 0.0, **TOL)
    # warm-up: NaN até existirem `length` deltas
    assert rsi(subida, 14).iloc[:14].isna().all()


# ------------------------------ TR / ATR ------------------------------


def test_true_range_com_gap():
    h = pd.Series([10.0, 12.0, 20.0])
    lo = pd.Series([9.0, 11.0, 19.0])
    c = pd.Series([9.5, 11.5, 19.5])
    out = true_range(h, lo, c)
    # barra 0: high-low; barra 2: gap de alta -> |high - close_anterior| domina
    np.testing.assert_allclose(out.to_numpy(), [1.0, 2.5, 8.5], **TOL)


@pytest.mark.parametrize("length", [7, 14])
def test_atr_vs_referencia(candles, length):
    expected = _atr_ref(
        candles["high"].to_numpy(), candles["low"].to_numpy(), candles["close"].to_numpy(), length
    )
    out = atr(candles["high"], candles["low"], candles["close"], length)
    np.testing.assert_allclose(out.to_numpy(), expected, **TOL)


def test_atr_range_constante():
    """Candles sem gaps com high-low = 2 fixo -> ATR = 2 após a semente."""
    n = 50
    c = pd.Series(np.full(n, 10.0))
    out = atr(c + 1.0, c - 1.0, c, 14)
    np.testing.assert_allclose(out.iloc[13:].to_numpy(), np.full(n - 13, 2.0), **TOL)


# ------------------------------- Pivôs --------------------------------


def test_pivot_high_confirmacao():
    """Pico em t=5 com left=right=3 -> confirmado exatamente em t=8."""
    h = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 9.0, 4.0, 3.0, 2.0, 1.0, 0.5])
    out = pivot_high(h, 3, 3)
    assert out.notna().sum() == 1
    assert out.index[out.notna()][0] == 8
    np.testing.assert_allclose(out.iloc[8], 9.0, **TOL)


def test_pivot_low_confirmacao():
    lo = pd.Series([9.0, 8.0, 7.0, 1.0, 7.0, 8.0, 9.0])
    out = pivot_low(lo, 3, 3)
    assert out.notna().sum() == 1
    np.testing.assert_allclose(out.iloc[6], 1.0, **TOL)


def test_pivot_plato_nao_gera_pivo():
    """Dois topos iguais (platô) não formam pivô (comparação estrita do Pine)."""
    h = pd.Series([1.0, 2.0, 5.0, 5.0, 2.0, 1.0, 0.5, 0.4])
    assert pivot_high(h, 2, 2).isna().all()


def test_pivot_serie_curta_sem_pivo():
    assert pivot_high(pd.Series([1.0, 2.0, 1.0]), 5, 5).isna().all()


def test_pivots_multiplos_em_zigzag(candles):
    """Em dados reais-sintéticos: todo pivô confirmado é de fato o extremo
    estrito da sua janela (verificação exaustiva, sem look-ahead)."""
    left = right = 5
    out = pivot_high(candles["high"], left, right)
    confirmados = np.where(out.notna().to_numpy())[0]
    assert len(confirmados) > 0
    h = candles["high"].to_numpy()
    for t in confirmados:
        p = t - right
        janela = h[p - left : p + right + 1]
        assert h[p] == janela.max()
        assert (janela == h[p]).sum() == 1
        np.testing.assert_allclose(out.iloc[t], h[p], **TOL)


# ------------------------ Donchian / MACD / Supertrend ----------------------


def test_donchian_vs_referencia(candles):
    h, lo = candles["high"], candles["low"]
    for length in (20, 55):
        esperado_h = [h.iloc[max(0, i - length + 1): i + 1].max() if i >= length - 1 else np.nan
                      for i in range(len(h))]
        np.testing.assert_allclose(
            donchian_high(h, length).to_numpy(), np.array(esperado_h), **TOL
        )
        esperado_l = [lo.iloc[max(0, i - length + 1): i + 1].min() if i >= length - 1 else np.nan
                      for i in range(len(lo))]
        np.testing.assert_allclose(
            donchian_low(lo, length).to_numpy(), np.array(esperado_l), **TOL
        )


def test_macd_identidade_com_emas(candles):
    line, signal, hist = macd(candles["close"], 12, 26, 9)
    np.testing.assert_allclose(
        line.to_numpy(),
        (ema(candles["close"], 12) - ema(candles["close"], 26)).to_numpy(), **TOL,
    )
    np.testing.assert_allclose(signal.to_numpy(), ema(line, 9).to_numpy(), **TOL)
    np.testing.assert_allclose(hist.to_numpy(), (line - signal).to_numpy(), **TOL)


def test_supertrend_invariantes(candles):
    line, trend = supertrend(candles["high"], candles["low"], candles["close"], 10, 3.0)
    validos = trend.notna()
    assert validos.sum() > 900
    c = candles["close"][validos]
    li, tr = line[validos], trend[validos]
    # tendência +1 <-> linha abaixo do preço; -1 <-> acima
    assert ((tr == 1) == (li <= c)).all()
    assert set(tr.unique()) <= {1.0, -1.0}
    # dentro de uma tendência de alta a linha nunca desce (ratchet)
    sobe = (tr == 1) & (tr.shift(1) == 1)
    assert (li.diff()[sobe] >= -1e-9).all()
    desce = (tr == -1) & (tr.shift(1) == -1)
    assert (li.diff()[desce] <= 1e-9).all()


def test_supertrend_flip_em_tendencia_obvia():
    n = 120
    up = pd.Series(np.linspace(100.0, 200.0, n))
    candles_up = dict(high=up + 1, low=up - 1, close=up)
    _, trend_up = supertrend(**candles_up, atr_len=10, mult=3.0)
    assert (trend_up.iloc[30:] == 1).all()  # subida sustentada -> alta

    seq = np.concatenate([np.linspace(100.0, 200.0, 60), np.linspace(200.0, 80.0, 60)])
    s = pd.Series(seq)
    _, trend = supertrend(s + 1, s - 1, s, atr_len=10, mult=3.0)
    assert (trend.iloc[30:55] == 1).all()
    assert (trend.iloc[-30:] == -1).all()  # queda forte vira baixa
