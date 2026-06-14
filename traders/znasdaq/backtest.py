"""Backtest runner for znasdaq.

Data: Yahoo Finance chart API for the synthetic-perp proxies (GC=F, ^GSPC,
SI=F, NVDA), wrapped in a disk cache (`.cache/`). Yahoo retention: 1h/4h
(4h is resampled from 1h) cover the full 180-day window; 5m/15m only cover
the most recent ~60 days — gates degrade gracefully (return "Insufficient
candle history") for the older portion, so the 5m/15m confirmation gates
simply don't fire until the last ~60 days of the run.
"""

from pathlib import Path
import yaml

from model_trader import CachingDataAdapter, YahooFinanceAdapter
from model_trader.backtest import run_backtest
from model_trader.logging import logger

from scanner import Scanner


YAHOO_SYMBOL_MAP = {
    "xyz:GOLD": "GC=F",
    "xyz:SP500": "^GSPC",
    "xyz:SILVER": "SI=F",
    "xyz:NVDA": "NVDA",
}


def main():
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    data = CachingDataAdapter(
        YahooFinanceAdapter(symbol_map=YAHOO_SYMBOL_MAP),
        cache_dir=Path(__file__).parent / ".cache",
    )

    results = run_backtest(
        scanner_factory=Scanner,
        config=config,
        data_adapter=data,
        days=180,
        step_timeframe="1h",
    )

    logger.info(f"Total: {results['total_trades']} trades")
    logger.info(f"W/L: {results['wins']}/{results['losses']} "
          f"({results['win_rate']}% WR)")
    logger.info(f"Total R: {results['total_r']}")
    logger.info(f"Avg R: {results['avg_r']}")
    logger.info(f"Profit factor: {results['profit_factor']}")


if __name__ == "__main__":
    main()
