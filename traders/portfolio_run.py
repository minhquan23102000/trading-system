"""Live portfolio monitor.

Which traders run is controlled by traders/portfolio.yaml — no code changes
needed when adding or removing a trader.

Run:
    uv run python traders/portfolio_run.py

For live trading set paper_trading: false in portfolio.yaml and export:
    HL_WALLET       0x...  main wallet address
    HL_PRIVATE_KEY  0x...  API wallet private key (trade permission only)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))  # ensure traders/ is importable
from utils import load_cfg, load_scanner

from model_trader import HyperliquidAdapter, PaperTrader, run_monitor
from model_trader.portfolio import PortfolioOrchestrator


ROOT = Path(__file__).parent


def main() -> None:
    with open(ROOT / "portfolio.yaml", encoding="utf-8") as f:
        pcfg = yaml.safe_load(f)

    # traders: list of {name, seed_pf, seed_n} or plain strings (backward compat)
    raw_traders = pcfg["traders"]
    trader_entries = [
        e if isinstance(e, dict) else {"name": e}
        for e in raw_traders
    ]
    trader_names = [e["name"] for e in trader_entries]
    seeds = {
        e["name"]: {"pf": e.get("seed_pf", 0.0), "n": e.get("seed_n", 0)}
        for e in trader_entries
    }

    paper_trading: bool = pcfg.get("paper_trading", True)
    starting_balance: float = pcfg.get("paper_balance", 100_000.0)
    journal = ROOT / pcfg.get("journal", "portfolio_trades.json")
    scan_interval: int = pcfg.get("scan_interval_seconds", 60)

    data = HyperliquidAdapter()

    scanners = {
        name: load_scanner(ROOT / name)(load_cfg(ROOT / name), data)
        for name in trader_names
    }

    if paper_trading:
        trader = PaperTrader(
            journal_path=journal,
            starting_balance=starting_balance,
            per_trade_pct=1.0,  # overridden per-trade by orchestrator
            max_leverage=pcfg.get("max_leverage", 25),
            data_adapter=data,
        )
    else:
        from model_trader.trading.live import HyperliquidExecutor  # noqa: PLC0415

        trader = HyperliquidExecutor(
            journal_path=journal,
            wallet_address=os.environ["HL_WALLET"],
            api_private_key=os.environ["HL_PRIVATE_KEY"],
            testnet=pcfg.get("testnet", True),
            per_trade_pct=1.0,
        )

    orch = PortfolioOrchestrator(
        scanners=scanners,
        trader=trader,
        starting_balance=starting_balance,
        seeds=seeds,
    )

    title = "Portfolio Monitor  [" + " + ".join(trader_names) + "]"
    run_monitor(
        scanner=None,
        trader=trader,
        portfolio=orch,
        scan_interval=scan_interval,
        title=title,
    )


if __name__ == "__main__":
    main()
