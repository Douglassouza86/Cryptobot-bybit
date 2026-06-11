"""T0.6 — Imprime o relatório de integridade do cache local.

Uso: uv run python scripts/check_data.py  (exit 0 = íntegro)
"""

import sys

import pandas as pd

from cryptobot.config import load_data_config
from cryptobot.data.downloader import funding_path, kline_path
from cryptobot.data.integrity import check_funding, check_klines


def main() -> int:
    cfg = load_data_config()
    all_ok = True
    for symbol in cfg.pairs:
        klines = pd.read_parquet(kline_path(cfg.data_dir, symbol))
        funding = pd.read_parquet(funding_path(cfg.data_dir, symbol))
        for report in (
            check_klines(klines, name=f"{symbol} klines"),
            check_funding(funding, klines=klines, name=f"{symbol} funding"),
        ):
            print(report)
            all_ok &= report.ok
    print("INTEGRIDADE: OK" if all_ok else "INTEGRIDADE: FALHOU")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
