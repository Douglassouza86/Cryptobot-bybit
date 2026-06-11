"""Validação de integridade do cache local de dados (T0.6 — gate da Fase 0).

A exchange é a fonte de verdade; aqui garantimos que o NOSSO cache é
contínuo, ordenado, sem duplicatas e com OHLC coerente antes de qualquer
backtest consumir esses dados.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from cryptobot.data.client import KLINE_COLUMNS

FUNDING_STEP = pd.Timedelta(hours=8)
FUNDING_HOURS_UTC = {0, 8, 16}
# Sanidade: funding de 8h fora de ±1% indica dado corrompido
MAX_ABS_FUNDING = 0.01


@dataclass
class IntegrityReport:
    name: str
    n_rows: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    issues: list[str]

    @property
    def ok(self) -> bool:
        return not self.issues

    def __str__(self) -> str:
        status = "OK" if self.ok else "FALHAS: " + " | ".join(self.issues)
        return f"[{self.name}] {self.n_rows} registros ({self.first} -> {self.last}) {status}"


def _base_index_issues(frame: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if str(frame.index.tz) != "UTC":
        issues.append("índice não está em UTC")
    if not frame.index.is_monotonic_increasing:
        issues.append("índice fora de ordem cronológica")
    if frame.index.has_duplicates:
        issues.append("timestamps duplicados")
    return issues


def check_klines(frame: pd.DataFrame, name: str = "klines") -> IntegrityReport:
    """Série horária contínua, sem NaN e com OHLC internamente coerente."""
    issues = _base_index_issues(frame)

    diffs = frame.index.to_series().diff().dropna()
    gaps = diffs[diffs != pd.Timedelta(hours=1)]
    if len(gaps):
        issues.append(f"{len(gaps)} gap(s) na série horária (primeiro em {gaps.index[0]})")

    if frame[KLINE_COLUMNS].isna().any().any():
        issues.append("valores NaN")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        issues.append("preços não-positivos")
    if (frame["volume"] < 0).any():
        issues.append("volume negativo")

    bad_high = frame["high"] < frame[["open", "close", "low"]].max(axis=1)
    bad_low = frame["low"] > frame[["open", "close", "high"]].min(axis=1)
    n_bad = int((bad_high | bad_low).sum())
    if n_bad:
        issues.append(f"{n_bad} candle(s) com OHLC incoerente")

    return IntegrityReport(
        name, len(frame), frame.index.min() if len(frame) else None,
        frame.index.max() if len(frame) else None, issues,
    )


def check_funding(
    frame: pd.DataFrame, klines: pd.DataFrame | None = None, name: str = "funding"
) -> IntegrityReport:
    """Grade de 8h alinhada a 00/08/16 UTC, contínua, com taxas plausíveis.

    Se `klines` for dado, valida cobertura: o funding pode começar antes dos
    klines (arquivo da Bybit), mas deve acompanhar a série até o fim.
    """
    issues = _base_index_issues(frame)

    misaligned = [
        ts for ts in frame.index
        if ts.hour not in FUNDING_HOURS_UTC or ts.minute or ts.second
    ]
    if misaligned:
        issues.append(f"{len(misaligned)} registro(s) fora da grade 00/08/16 UTC")

    diffs = frame.index.to_series().diff().dropna()
    gaps = diffs[diffs != FUNDING_STEP]
    if len(gaps):
        issues.append(f"{len(gaps)} gap(s) na grade de 8h (primeiro em {gaps.index[0]})")

    if frame["funding_rate"].isna().any():
        issues.append("valores NaN")
    if (frame["funding_rate"].abs() > MAX_ABS_FUNDING).any():
        issues.append(f"funding fora de ±{MAX_ABS_FUNDING:.0%}")

    if klines is not None and len(klines) and len(frame):
        if frame.index.min() > klines.index.min() + FUNDING_STEP:
            issues.append("funding começa depois do início dos klines")
        if frame.index.max() < klines.index.max() - FUNDING_STEP:
            issues.append("funding termina antes do fim dos klines")

    return IntegrityReport(
        name, len(frame), frame.index.min() if len(frame) else None,
        frame.index.max() if len(frame) else None, issues,
    )
