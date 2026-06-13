"""Download incremental de klines e funding para cache local em Parquet.

Idempotente: re-executar baixa apenas o delta desde o último registro salvo;
sem dados novos, os arquivos não são tocados (RF-001/RF-002).
Somente candles FECHADOS entram no cache.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from cryptobot.data.client import INTERVAL_MS, BybitMarketData

logger = logging.getLogger(__name__)


# sufixo de arquivo por intervalo da API V5
INTERVAL_SUFFIX = {"5": "5m", "15": "15m", "60": "1h", "240": "4h", "D": "1d"}


def kline_path(data_dir: Path, symbol: str, interval: str = "60") -> Path:
    return data_dir / f"{symbol}_{INTERVAL_SUFFIX[interval]}.parquet"


def funding_path(data_dir: Path, symbol: str) -> Path:
    return data_dir / f"{symbol}_funding.parquet"


def last_closed_boundary_ms(interval: str = "60") -> int:
    """Início (ms UTC) do candle corrente — tudo ANTES disso está fechado."""
    step = INTERVAL_MS[interval]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return (now_ms // step) * step


def _merge_and_save(
    existing: pd.DataFrame | None, fresh: pd.DataFrame, path: Path
) -> pd.DataFrame:
    combined = fresh if existing is None else pd.concat([existing, fresh])
    combined = combined[~combined.index.duplicated(keep="first")].sort_index()
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path)
    return combined


def update_klines(
    client: BybitMarketData,
    symbol: str,
    start: datetime,
    data_dir: Path,
    interval: str = "60",
) -> pd.DataFrame:
    """Baixa/atualiza klines de `start` até o último candle fechado."""
    path = kline_path(data_dir, symbol, interval)
    end_ms = last_closed_boundary_ms(interval)
    start_ms = int(start.timestamp() * 1000)

    existing: pd.DataFrame | None = None
    if path.exists():
        existing = pd.read_parquet(path)
        if len(existing):
            last_saved_ms = int(existing.index[-1].timestamp() * 1000)
            start_ms = last_saved_ms + INTERVAL_MS[interval]

    if start_ms >= end_ms:
        logger.info("%s klines: cache atualizado (%d candles)", symbol, len(existing))
        return existing

    fresh = client.get_klines(symbol, start_ms, end_ms, interval)
    combined = _merge_and_save(existing, fresh, path)
    logger.info("%s klines: +%d candles (total %d)", symbol, len(fresh), len(combined))
    return combined


def update_funding(
    client: BybitMarketData,
    symbol: str,
    start: datetime,
    data_dir: Path,
) -> pd.DataFrame:
    """Baixa/atualiza o histórico de funding de `start` até agora."""
    path = funding_path(data_dir, symbol)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int(start.timestamp() * 1000)

    existing: pd.DataFrame | None = None
    if path.exists():
        existing = pd.read_parquet(path)
        if len(existing):
            start_ms = int(existing.index[-1].timestamp() * 1000) + 1

    if start_ms >= end_ms:
        logger.info("%s funding: cache atualizado (%d registros)", symbol, len(existing))
        return existing

    fresh = client.get_funding_history(symbol, start_ms, end_ms)
    if existing is not None and fresh.empty:
        logger.info("%s funding: sem registros novos (%d salvos)", symbol, len(existing))
        return existing

    combined = _merge_and_save(existing, fresh, path)
    logger.info("%s funding: +%d registros (total %d)", symbol, len(fresh), len(combined))
    return combined
