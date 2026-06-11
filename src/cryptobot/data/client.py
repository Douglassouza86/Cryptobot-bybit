"""Cliente de market data da Bybit (API V5, endpoints públicos).

Fases 0-1 usam apenas dados públicos — nenhuma chave de API é necessária.
Endpoints: GET /v5/market/kline e GET /v5/market/funding/history (via pybit).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import pandas as pd
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)

# Máximo de registros por request (API V5)
KLINE_LIMIT = 1000
FUNDING_LIMIT = 200

# Duração de cada intervalo da API em milissegundos
INTERVAL_MS = {
    "1": 60_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "240": 14_400_000,
    "D": 86_400_000,
}

KLINE_COLUMNS = ["open", "high", "low", "close", "volume", "turnover"]


class BybitMarketData:
    """Wrapper fino sobre o pybit: paginação, retry com backoff e saída em DataFrame.

    Todos os timestamps são UTC. Retorna apenas candles dentro da janela pedida,
    ordenados e sem duplicatas — o chamador decide o corte de candle fechado.
    """

    def __init__(self, max_retries: int = 5, backoff_base: float = 1.0) -> None:
        self._http = HTTP()  # market data público: sem autenticação
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    # ------------------------------------------------------------------ retry

    def _call(self, fn: Callable[..., dict[str, Any]], **params: Any) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = fn(**params)
                ret_code = resp.get("retCode")
                if ret_code != 0:
                    raise RuntimeError(f"Bybit retCode={ret_code}: {resp.get('retMsg')}")
                return resp["result"]
            except Exception as exc:  # rede, rate limit, 5xx, retCode != 0
                last_exc = exc
                wait = self._backoff_base * (2**attempt)
                logger.warning("Chamada Bybit falhou (%s); retry em %.1fs", exc, wait)
                time.sleep(wait)
        raise RuntimeError(
            f"Bybit: esgotadas {self._max_retries} tentativas ({params.get('symbol')})"
        ) from last_exc

    # ----------------------------------------------------------------- klines

    def get_klines(
        self, symbol: str, start_ms: int, end_ms: int, interval: str = "60"
    ) -> pd.DataFrame:
        """Baixa klines no intervalo [start_ms, end_ms) paginando para frente.

        Pagina apenas com `start` (sem `end`) para evitar ambiguidade da API
        quando a janela excede o limite por request; o corte em `end_ms` é local.
        """
        step_ms = INTERVAL_MS[interval]
        rows: list[list[str]] = []
        cursor = start_ms
        while cursor < end_ms:
            result = self._call(
                self._http.get_kline,
                category="linear",
                symbol=symbol,
                interval=interval,
                start=cursor,
                limit=KLINE_LIMIT,
            )
            batch = result.get("list", [])
            if not batch:
                break
            batch.reverse()  # API retorna descendente; passamos a ascendente
            rows.extend(batch)
            newest_ms = int(batch[-1][0])
            next_cursor = newest_ms + step_ms
            if next_cursor <= cursor:  # proteção contra loop infinito
                break
            cursor = next_cursor
        return _klines_to_frame(rows, end_ms)

    # ---------------------------------------------------------------- funding

    def get_funding_history(self, symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
        """Baixa o histórico de funding em [start_ms, end_ms] paginando para trás."""
        records: list[dict[str, str]] = []
        cursor_end = end_ms
        while cursor_end > start_ms:
            result = self._call(
                self._http.get_funding_rate_history,
                category="linear",
                symbol=symbol,
                startTime=start_ms,
                endTime=cursor_end,
                limit=FUNDING_LIMIT,
            )
            batch = result.get("list", [])
            if not batch:
                break
            records.extend(batch)
            oldest_ms = min(int(r["fundingRateTimestamp"]) for r in batch)
            if oldest_ms <= start_ms or len(batch) < FUNDING_LIMIT:
                break
            cursor_end = oldest_ms - 1
        return _funding_to_frame(records, start_ms)


def _klines_to_frame(rows: list[list[str]], end_ms: int) -> pd.DataFrame:
    """Normaliza linhas da API em DataFrame OHLCV indexado por timestamp UTC."""
    if not rows:
        return pd.DataFrame(columns=KLINE_COLUMNS, index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.DataFrame(rows, columns=["timestamp", *KLINE_COLUMNS])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms", utc=True)
    frame = frame.set_index("timestamp")
    frame = frame.astype("float64")
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    # Corte local: somente candles que ABREM antes de end_ms (fechados, por construção
    # do chamador, que passa end_ms = início da hora corrente)
    return frame[frame.index < pd.to_datetime(end_ms, unit="ms", utc=True)]


def _funding_to_frame(records: list[dict[str, str]], start_ms: int) -> pd.DataFrame:
    """Normaliza registros de funding em DataFrame indexado por timestamp UTC."""
    if not records:
        return pd.DataFrame(columns=["funding_rate"], index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.DataFrame(records)
    frame["timestamp"] = pd.to_datetime(
        frame["fundingRateTimestamp"].astype("int64"), unit="ms", utc=True
    )
    frame["funding_rate"] = frame["fundingRate"].astype("float64")
    frame = frame.set_index("timestamp")[["funding_rate"]]
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    return frame[frame.index >= pd.to_datetime(start_ms, unit="ms", utc=True)]
