"""Backtest runner for tradingnotes.

Data: Binance spot klines (BTCUSDT/ETHUSDT/SOLUSDT/BNBUSDT), wrapped in a
disk cache (`.cache/`) so repeated runs only fetch the gap since last run.
Binance has years of history at every configured interval, so the backtest
covers 180 days.
"""

from pathlib import Path
import yaml

from model_trader import BinanceAdapter, CachingDataAdapter
from model_trader.backtest import run_backtest
from model_trader.logging import logger

from scanner import Scanner


def main():
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    data = CachingDataAdapter(BinanceAdapter(), cache_dir=Path(__file__).parent / ".cache")

    results = run_backtest(
        scanner_factory=Scanner,
        config=config,
        data_adapter=data,
        days=180,
        evaluate_every_n_bars=3,  # check every 15m; 1H/5M structure doesn't shift bar-by-bar
    )

    logger.info(f"Total: {results['total_trades']} trades")
    logger.info(f"W/L: {results['wins']}/{results['losses']} "
          f"({results['win_rate']}% WR)")
    logger.info(f"Total R: {results['total_r']}")
    logger.info(f"Avg R: {results['avg_r']}")
    logger.info(f"Profit factor: {results['profit_factor']}")


if __name__ == "__main__":
    main()
