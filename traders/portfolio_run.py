"""Live portfolio monitor: tradingnotes + znasdaq + mulham.

Run:
    uv run python traders/portfolio_run.py

Requires:
    traders/tradingnotes/config.yaml  paper_trading: true   (or false for live)
    traders/znasdaq/config.yaml
    traders/mulham/config.yaml

For live trading (paper_trading: false in any config), set env vars:
    HL_WALLET       0x...  main wallet address
    HL_PRIVATE_KEY  0x...  API wallet private key (trade permission only)

All three traders share a single journal at traders/portfolio_trades.json.
Balance and composite scores are computed from this shared journal.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import yaml

from model_trader import HyperliquidAdapter, PaperTrader, run_monitor
from model_trader.portfolio import PortfolioOrchestrator


ROOT = Path(__file__).parent
JOURNAL = ROOT / "portfolio_trades.json"


def _load_scanner(name: str):
    """Load Scanner class from traders/<name>/scanner.py without requiring a package."""
    spec = importlib.util.spec_from_file_location(
        f"_scanner_{name}", ROOT / name / "scanner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Scanner


def _load_cfg(name: str) -> dict:
    with open(ROOT / name / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    tn_cfg = _load_cfg("tradingnotes")
    zn_cfg = _load_cfg("znasdaq")
    ml_cfg = _load_cfg("mulham")

    data = HyperliquidAdapter()

    tn_scanner = _load_scanner("tradingnotes")(tn_cfg, data)
    zn_scanner = _load_scanner("znasdaq")(zn_cfg, data)
    ml_scanner = _load_scanner("mulham")(ml_cfg, data)

    # All three configs must agree on paper_trading mode.
    # Use tradingnotes as the authority.
    paper_trading = tn_cfg.get("paper_trading", True)
    starting_balance = tn_cfg.get("paper_balance", 100_000.0)

    if paper_trading:
        trader = PaperTrader(
            journal_path=JOURNAL,
            starting_balance=starting_balance,
            per_trade_pct=1.0,  # overridden per-trade by orchestrator
            max_leverage=tn_cfg.get("max_leverage", 25),
            data_adapter=data,
        )
    else:
        from model_trader.executor import HyperliquidExecutor  # noqa: PLC0415

        trader = HyperliquidExecutor(
            journal_path=JOURNAL,
            wallet_address=os.environ["HL_WALLET"],
            api_private_key=os.environ["HL_PRIVATE_KEY"],
            testnet=tn_cfg.get("testnet", True),
            per_trade_pct=1.0,
        )

    orch = PortfolioOrchestrator(
        scanners={
            "tradingnotes": tn_scanner,
            "znasdaq": zn_scanner,
            "mulham": ml_scanner,
        },
        trader=trader,
        starting_balance=starting_balance,
    )

    run_monitor(
        scanner=None,
        paper_trader=trader,
        portfolio=orch,
        scan_interval=tn_cfg.get("scan_interval_seconds", 60),
        title="Portfolio Monitor  [tradingnotes + znasdaq + mulham]",
    )


if __name__ == "__main__":
    main()
