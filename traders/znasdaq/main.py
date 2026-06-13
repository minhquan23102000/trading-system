"""Entry point for znasdaq. Runs the live monitor."""

from pathlib import Path
import yaml

from model_trader import HyperliquidAdapter, PaperTrader, run_monitor

from scanner import Scanner


HERE = Path(__file__).parent


def main():
    with open(HERE / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    data = HyperliquidAdapter()
    scanner = Scanner(config, data)

    paper = PaperTrader(
        journal_path=HERE / "trades.json",
        starting_balance=config.get("paper_balance", 100_000),
        per_trade_pct=config.get("per_trade_percent", 1.0),
        max_leverage=config.get("max_leverage", 25),
        data_adapter=data,
    )

    run_monitor(
        scanner=scanner,
        paper_trader=paper,
        scan_interval=config.get("scan_interval_seconds", 60),
        title="znasdaq Live Monitor",
    )


if __name__ == "__main__":
    main()
