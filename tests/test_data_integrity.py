"""T0.6 — Gate da Fase 0: integridade do cache real de dados.

Roda sobre os parquets baixados por scripts/download_data.py.
Se o cache ainda não existe, os testes são pulados (rode o download antes).
"""

import pandas as pd
import pytest

from cryptobot.config import load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.data.integrity import check_funding, check_klines

CFG = load_data_config()

# Início real do arquivo da Bybit (perpétuos lineares) — verificado na API em 2026-06-11:
# a exchange não tem dados anteriores a estas datas, apesar do PRD assumir 2020-01-01.
EXPECTED_START = {
    "BTCUSDT": pd.Timestamp("2020-03-25 10:00", tz="UTC"),
    "ETHUSDT": pd.Timestamp("2021-03-15 00:00", tz="UTC"),
}
MIN_CANDLES = {"BTCUSDT": 50_000, "ETHUSDT": 40_000}


def _load(path):
    if not path.exists():
        pytest.skip(f"cache ausente: {path} (rode scripts/download_data.py)")
    return pd.read_parquet(path)


@pytest.fixture(scope="module", params=CFG.pairs)
def symbol(request) -> str:
    return request.param


def test_klines_integros(symbol: str):
    frame = _load(kline_path(CFG.data_dir, symbol))
    report = check_klines(frame, name=f"{symbol} klines")
    print(report)
    assert report.ok, str(report)
    assert len(frame) >= MIN_CANDLES[symbol]
    assert frame.index.min() == EXPECTED_START[symbol]


def test_funding_integro(symbol: str):
    klines = _load(kline_path(CFG.data_dir, symbol))
    funding = _load(funding_path(CFG.data_dir, symbol))
    report = check_funding(funding, klines=klines, name=f"{symbol} funding")
    print(report)
    assert report.ok, str(report)
