"""T0.4/T0.5 — Baixa/atualiza o cache local de klines e funding.

Uso:  uv run python scripts/download_data.py
Config: config/data.yaml. Idempotente — pode rodar quantas vezes quiser.
"""

import logging
import sys

from cryptobot.config import load_data_config
from cryptobot.data.client import BybitMarketData
from cryptobot.data.downloader import update_funding, update_klines


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    cfg = load_data_config()
    client = BybitMarketData()

    for symbol in cfg.pairs:
        for interval in cfg.intervals:
            klines = update_klines(client, symbol, cfg.start, cfg.data_dir, interval)
            print(
                f"{symbol} [{interval}]: {len(klines)} candles "
                f"({klines.index[0]} -> {klines.index[-1]})"
            )
        funding = update_funding(client, symbol, cfg.start, cfg.data_dir)
        print(f"{symbol}: {len(funding)} registros de funding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
