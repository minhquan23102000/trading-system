"""Shared trade-journal primitives.

JSON persistence, risk-based position sizing, and close/PnL accounting used by
both `PaperTrader` (simulated fills) and live executors (e.g.
`HyperliquidExecutor`, real fills). Keeping this math in one place means paper
and live sizing/PnL can never drift apart.

Also defines `Trader`, the structural (duck-typed) contract both
`PaperTrader` and live executors already satisfy: `execute`, `check_exits`,
`get_open_trades`, `get_all_trades`, `get_balance`. `PortfolioOrchestrator`
and a trader's `main.py` can type against `Trader` and swap implementations
freely.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


def load_journal(path: Path) -> list[dict]:
    """Read the JSON trade journal at `path`, or `[]` if it doesn't exist yet."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_journal(path: Path, trades: list[dict]) -> None:
    """Write `trades` to `path` as JSON, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, default=str)


def size_with_leverage_cap(
    balance: float,
    risk_pct: float,
    entry: float,
    stop_dist: float,
    max_leverage: float,
) -> tuple[float, float]:
    """Risk-based position size, capped so notional <= balance * max_leverage.

    Returns `(size, risk_amount)`. `risk_amount` is shrunk along with `size`
    when the leverage cap binds, so it always reflects the actual position.
    """
    risk = balance * (risk_pct / 100)
    size = risk / stop_dist

    notional = size * entry
    max_notional = balance * max_leverage
    if notional > max_notional:
        size = max_notional / entry
        risk = size * stop_dist

    return size, risk


def apply_close(
    trade: dict[str, Any],
    reason: str,
    exit_price: float,
    exit_time: str | None = None,
) -> None:
    """Mutate `trade` in place with closed-state fields.

    Sets `status`, `exit_time`, `exit_price`, `pnl`, `r_multiple`, `outcome`,
    and `notes` (= `reason`, e.g. "SL_HIT" / "TP_HIT" / "MANUAL").
    """
    trade["status"] = "CLOSED"
    trade["exit_time"] = exit_time or datetime.now(timezone.utc).isoformat()
    trade["exit_price"] = exit_price

    if trade["direction"] == "long":
        trade["pnl"] = (exit_price - trade["entry_price"]) * trade["position_size"]
    else:
        trade["pnl"] = (trade["entry_price"] - exit_price) * trade["position_size"]

    stop_dist = abs(trade["entry_price"] - trade["stop_loss"])
    if stop_dist > 0:
        trade["r_multiple"] = round(
            trade["pnl"] / (trade["position_size"] * stop_dist), 2
        )
    else:
        trade["r_multiple"] = 0

    if trade["pnl"] > 0:
        trade["outcome"] = "WIN"
    elif trade["pnl"] < 0:
        trade["outcome"] = "LOSS"
    else:
        trade["outcome"] = "BE"

    trade["notes"] = reason


@runtime_checkable
class Trader(Protocol):
    """Structural contract shared by `PaperTrader` and live executors.

    Both `PaperTrader` and `HyperliquidExecutor` already implement this
    surface without inheriting from it (duck typing). Use it as a type
    annotation — e.g. `PortfolioOrchestrator(trader: Trader, ...)` or in a
    trader's `main.py` — to swap paper/live implementations without changing
    call sites.
    """

    def execute(self, setup: Any) -> Any: ...

    def check_exits(self) -> list[dict]: ...

    def get_open_trades(self) -> list[dict]: ...

    def get_all_trades(self) -> list[dict]: ...

    def get_balance(self) -> float: ...
