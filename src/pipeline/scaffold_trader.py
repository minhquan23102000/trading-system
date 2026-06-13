"""Scaffold a new trader project.

Creates a `traders/<name>/` directory with boilerplate:
    - scanner.py    — template scanner (subclass of ScannerBase)
    - config.yaml   — default config (symbols, timeframes)
    - main.py       — entry point for running the monitor
    - philosophy.md — copy of the template for the optional agent layer
    - backtest.py   — backtest runner

Usage:
    python -m pipeline.scaffold_trader <trader_name>
    python -m pipeline.scaffold_trader my_trader

The `traders/` directory is gitignored by default — it holds trader-specific
state (transcripts, trades.json) that shouldn't be committed.
"""

from __future__ import annotations

import sys
from pathlib import Path


SCANNER_TEMPLATE = '''"""Scanner for {name}.

Implements this trader's strategy as a gate pipeline. Each gate is a
pass/fail check. If any gate fails, the setup is SKIP or WAIT. Only when
all gates pass does the scanner return TAKE with entry/stop/target set.

See docs/designing-gates.md for guidance on how to translate a strategy
document into gate logic.
"""

from __future__ import annotations

from model_trader.gates import ScannerBase, SetupResult, SetupStatus
from model_trader.detectors import (
    # Class-based (recommended — configure once, reuse):
    SwingDetector,
    FVGDetector,
    FailureSwingDetector,
    CISDDetector,
    SMTDetector,
    DisplacementDetector,
    # Legacy functions (still work for quick one-offs):
    detect_swings,
    detect_fvg,
    detect_failure_swings,
    detect_cisd,
    detect_smt,
    detect_displacement,
)


class Scanner(ScannerBase):
    """TODO: describe this trader's strategy in one sentence.

    Fill in the evaluate() method to implement the gate pipeline.
    See strategy.md (generated from transcripts) for the rules to encode.
    """

    def evaluate(self, symbol: str) -> SetupResult:
        result = SetupResult(symbol=symbol)

        data = self.fetch_data(symbol)
        if not data.get("1h") or not data.get("5m"):
            result.reason = "Missing data"
            return result

        # ===== GATE 1: [name] =====
        # TODO: implement first gate. Example patterns:
        #
        #   # Class-based (configure once in __init__):
        #   swing_detector = SwingDetector(lookback=5)
        #   swings = swing_detector.detect(data["1h"][-50:])
        #   # or: swings = swing_detector(data["1h"][-50:])
        #
        #   fvg_detector = FVGDetector()
        #   fvgs = fvg_detector.detect(data["1h"][-50:])
        #
        #   fail_detector = FailureSwingDetector(tolerance_pct=0.1)
        #   failure_swings = fail_detector.detect(swings)
        #
        #   if not failure_swings:
        #       result.reason = "No failure swings"
        #       return result
        #
        #   result.gates_passed.append("GATE1_NAME")

        # ===== GATE 2: [name] =====
        # TODO

        # ===== GATE N: protected stop =====
        # entry, stop, target must be set for a TAKE to be executed.
        #
        #   result.entry = entry_price
        #   result.stop = stop_price
        #   result.target = take_profit_price
        #   result.direction = "long" or "short"
        #   result.status = SetupStatus.TAKE
        #   result.reason = "All gates passed"

        return result

    def evaluate_at(self, symbol: str, hist: dict, corr_hist: dict, ts: int) -> SetupResult:
        """Backtest variant: same logic but uses pre-fetched historical data.

        The backtest runner walks through history chronologically and calls
        this with slices of `hist` truncated at each step timestamp. Your
        implementation should mirror evaluate() but read from `hist` instead
        of calling self.data.fetch_candles().

        See docs/backtest.md for the exact pattern.
        """
        raise NotImplementedError("Implement evaluate_at to support backtesting")
'''


CONFIG_TEMPLATE = '''# {name} trader configuration

symbols:
  # TODO: fill in with symbols this trader trades
  - "BTC"
  - "ETH"

timeframes:
  - 1m
  - 5m
  - 15m
  - 1h
  - 4h

correlations:
  # TODO: add correlation pairs for SMT divergence if used
  # "SYMBOL_A": "SYMBOL_B"

scan_interval_seconds: 60

# Paper trading
paper_trading: true
paper_balance: 100000.0
per_trade_percent: 1.0
max_leverage: 25

# Optional agent layer
agent_enabled: false
'''


MAIN_TEMPLATE = '''"""Entry point for {name}. Runs the live monitor."""

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
        title="{name} Live Monitor",
    )


if __name__ == "__main__":
    main()
'''


BACKTEST_TEMPLATE = '''"""Backtest runner for {name}."""

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
        days=7,
    )

    print(f"\\nTotal: {{results['total_trades']}} trades")
    print(f"W/L: {{results['wins']}}/{{results['losses']}} "
          f"({{results['win_rate']}}% WR)")
    print(f"Total R: {{results['total_r']}}")
    print(f"Avg R: {{results['avg_r']}}")
    print(f"Profit factor: {{results['profit_factor']}}")


if __name__ == "__main__":
    main()
'''


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m pipeline.scaffold_trader <trader_name>")
        sys.exit(1)

    name = sys.argv[1]
    target_dir = Path("traders") / name

    if target_dir.exists():
        print(f"Directory already exists: {target_dir}")
        sys.exit(1)

    target_dir.mkdir(parents=True)
    (target_dir / "transcripts").mkdir()

    (target_dir / "scanner.py").write_text(SCANNER_TEMPLATE.format(name=name), encoding="utf-8")
    (target_dir / "config.yaml").write_text(CONFIG_TEMPLATE.format(name=name), encoding="utf-8")
    (target_dir / "main.py").write_text(MAIN_TEMPLATE.format(name=name), encoding="utf-8")
    (target_dir / "backtest.py").write_text(BACKTEST_TEMPLATE.format(name=name), encoding="utf-8")

    print(f"Scaffolded {target_dir}\n")
    print("Next steps:")
    print(f"  1. Fetch transcripts: uv run python -m pipeline.fetch_youtube_transcripts {target_dir}/transcripts <video_ids...>")
    print(f"  2. Extract strategy:  uv run python -m pipeline.extract_strategy {target_dir}/transcripts {target_dir}")
    print(f"  3. Implement scanner:  edit {target_dir}/scanner.py (use strategy.md as reference)")
    print(f"  4. Configure symbols:  edit {target_dir}/config.yaml")
    print(f"  5. Run:                cd {target_dir} && uv run python main.py")


if __name__ == "__main__":
    main()
