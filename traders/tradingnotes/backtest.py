"""Backtest runner for tradingnotes."""

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
        days=30,
    )

    print(f"\nTotal: {results['total_trades']} trades")
    print(f"W/L: {results['wins']}/{results['losses']} "
          f"({results['win_rate']}% WR)")
    print(f"Total R: {results['total_r']}")
    print(f"Avg R: {results['avg_r']}")
    print(f"Profit factor: {results['profit_factor']}")


if __name__ == "__main__":
    main()
