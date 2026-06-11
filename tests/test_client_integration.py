"""T0.3 — Teste de integração do cliente Bybit (acessa a API real, dados públicos)."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from cryptobot.data.client import KLINE_COLUMNS, BybitMarketData

pytestmark = pytest.mark.integration

START = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2024, 1, 8, tzinfo=timezone.utc).timestamp() * 1000)  # 7 dias


@pytest.fixture(scope="module")
def client() -> BybitMarketData:
    return BybitMarketData()


def test_klines_uma_semana_btcusdt(client: BybitMarketData):
    frame = client.get_klines("BTCUSDT", START, END, interval="60")

    assert list(frame.columns) == KLINE_COLUMNS
    assert len(frame) == 168, "7 dias x 24h = 168 candles fechados"
    assert str(frame.index.tz) == "UTC"
    assert frame.index.is_monotonic_increasing
    assert not frame.index.has_duplicates
    # continuidade: exatamente 1h entre candles consecutivos
    assert (frame.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all()
    # sanidade OHLC
    assert (frame["high"] >= frame["low"]).all()
    assert (frame["high"] >= frame["close"]).all()
    assert (frame["low"] <= frame["open"]).all()


def test_funding_uma_semana_btcusdt(client: BybitMarketData):
    frame = client.get_funding_history("BTCUSDT", START, END)

    assert list(frame.columns) == ["funding_rate"]
    # janela inclusiva nas duas pontas: 01/01 00:00 ... 08/01 00:00 = 21 + 1 registros
    assert len(frame) == 22
    assert str(frame.index.tz) == "UTC"
    assert frame.index.is_monotonic_increasing
    # janelas alinhadas a 00/08/16 UTC
    assert set(frame.index.hour.unique()) <= {0, 8, 16}
    assert frame["funding_rate"].abs().max() < 0.01, "funding 1h fora de range plausível"
