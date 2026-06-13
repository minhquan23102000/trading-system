"""Backtest runner for mulham.

Data depth: Hyperliquid's candleSnapshot API has a hard 5,000-candle limit
per timeframe. At 5m that's ~17 days; at 15m it's ~52 days. We step on 15m
to maximize lookback. The scanner still uses 5m for the Gate 8 trigger candle
when available — it just steps forward on 15m bars between evaluations.
"""


from pathlib import Path
import yaml

from model_trader import HyperliquidAdapter
from model_trader.backtest import run_backtest

from scanner import Scanner


def main():
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    data = HyperliquidAdapter()

    results = run_backtest(
        scanner_factory=Scanner,
        config=config,
        data_adapter=data,
        days=52,
        step_timeframe="15m",
    )
    print(f"\nTotal: {results['total_trades']} trades")
    print(f"W/L: {results['wins']}/{results['losses']} "
          f"({results['win_rate']}% WR)")
    print(f"Total R: {results['total_r']}")
    print(f"Avg R: {results['avg_r']}")
    print(f"Profit factor: {results['profit_factor']}")

    print("\nPer-symbol R:")
    for sym, stats in results.get("per_symbol", {}).items():
        print(f"  {sym}: {stats['trades']} trades ({stats['wins']}W/{stats['losses']}L), R={stats['total_r']}")


if __name__ == "__main__":
    main()
