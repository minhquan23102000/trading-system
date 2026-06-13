"""Pure portfolio sizing functions.

No I/O, no external state - everything here is computed from arguments only.
These functions turn per-trader journal history and raw scanner decisions
into risk-sized, correlation-capped, portfolio-aware decisions.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from ..gates import SetupResult

_DEFAULT_GROUP_CAPS: dict[str, int] = {"CRYPTO": 2, "METALS": 1, "INDEX": 1}

_CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "BNB", "AVAX"}
_METAL_SYMBOLS = {"xyz:GOLD", "xyz:SILVER"}
_INDEX_SYMBOLS = {"xyz:SP500", "xyz:NVDA"}


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO8601 timestamp, normalizing naive datetimes to UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _profit_factor(trades: list[dict]) -> float:
    """Profit factor for a list of closed trades, clipped to [0.0, 10.0]."""
    gross_win = sum(t["pnl"] for t in trades if (t["pnl"] or 0) > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if (t["pnl"] or 0) < 0))
    if gross_loss > 0:
        pf = gross_win / gross_loss
    else:
        pf = 10.0 if gross_win > 0 else 1.0
    return max(0.0, min(10.0, pf))


def composite_from_journal(
    trades: list[dict],
    trader_id: str,
    window_days: int = 90,
    min_trades: int = 10,
) -> dict[str, Any]:
    """Compute a composite score for one trader from journal history.

    Returns ``{"composite": float, "n": int, "pf": float}`` where ``n`` is
    the number of closed trades for ``trader_id`` within ``window_days``.
    A stability bonus is applied when both the current and prior window
    have a profit factor above 1.2.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    prior_start = now - timedelta(days=2 * window_days)

    relevant = [
        t
        for t in trades
        if t.get("status") == "CLOSED"
        and t.get("extras", {}).get("trader_id") == trader_id
    ]

    window_trades = []
    prior_trades = []
    for t in relevant:
        exit_dt = _parse_iso(t.get("exit_time"))
        if exit_dt is None:
            continue
        if window_start <= exit_dt <= now:
            window_trades.append(t)
        elif prior_start <= exit_dt < window_start:
            prior_trades.append(t)

    n = len(window_trades)
    if n == 0:
        return {"composite": 0.0, "n": 0, "pf": 0.0}

    pf = _profit_factor(window_trades)
    prior_pf = _profit_factor(prior_trades)

    stability = 1.15 if pf > 1.2 and prior_pf > 1.2 else 1.0
    composite = pf * math.log(1 + n) * stability

    return {"composite": composite, "n": n, "pf": pf}


def compute_weights(
    composites: dict[str, dict],
    base_pct: float = 1.0,
    min_pct: float = 0.25,
    max_pct: float = 2.0,
    min_trades: int = 10,
) -> dict[str, float]:
    """Turn per-trader composites into risk_pct allocations.

    Traders below ``min_trades`` are not "graduated" - their effective
    composite is the mean of graduated traders' composites. If nobody has
    graduated, everyone gets ``base_pct``.
    """
    graduated = {tid: d for tid, d in composites.items() if d["n"] >= min_trades}

    if not graduated:
        return {tid: base_pct for tid in composites}

    mean_graduated = statistics.mean(d["composite"] for d in graduated.values())

    eff: dict[str, float] = {}
    for tid, d in composites.items():
        eff[tid] = d["composite"] if tid in graduated else mean_graduated

    mean_eff = statistics.mean(eff.values())
    if mean_eff == 0:
        return {tid: base_pct for tid in composites}

    weights: dict[str, float] = {}
    for tid, e in eff.items():
        w = e / mean_eff
        risk_pct = base_pct * w
        weights[tid] = max(min_pct, min(max_pct, risk_pct))

    return weights


def group_for(symbol: str) -> str:
    """Map a symbol to its correlation group."""
    if symbol in _CRYPTO_SYMBOLS:
        return "CRYPTO"
    if symbol in _METAL_SYMBOLS:
        return "METALS"
    if symbol in _INDEX_SYMBOLS:
        return "INDEX"
    return "OTHER"


def resolve_same_symbol(
    decisions: list[SetupResult],
    composites: dict[str, dict],
) -> list[SetupResult]:
    """Resolve multiple decisions on the same symbol.

    If 2+ decisions target the same symbol: when all agree on direction,
    keep only the one from the trader with the highest composite; when
    directions conflict, drop all of them.
    """
    by_symbol: dict[str, list[SetupResult]] = defaultdict(list)
    for d in decisions:
        by_symbol[d.symbol].append(d)

    result: list[SetupResult] = []
    for group in by_symbol.values():
        if len(group) < 2:
            result.extend(group)
            continue

        directions = {d.direction for d in group}
        if len(directions) == 1:
            best = max(
                group,
                key=lambda d: composites.get(d.extras.get("trader_id"), {}).get(
                    "composite", 0.0
                ),
            )
            result.append(best)
        # mixed directions: drop all decisions for this symbol

    return result


def apply_correlation_cap(
    decisions: list[SetupResult],
    open_trades: list[dict],
    group_caps: dict[str, int] | None = None,
) -> list[SetupResult]:
    """Drop decisions that would exceed per-group open-position caps."""
    if group_caps is None:
        group_caps = dict(_DEFAULT_GROUP_CAPS)

    open_count: dict[str, int] = {}
    for t in open_trades:
        if t.get("status") == "OPEN":
            g = group_for(t["symbol"])
            open_count[g] = open_count.get(g, 0) + 1

    accepted: list[SetupResult] = []
    for d in decisions:
        g = group_for(d.symbol)
        cap = group_caps.get(g)
        if cap is not None and open_count.get(g, 0) >= cap:
            continue
        accepted.append(d)
        open_count[g] = open_count.get(g, 0) + 1

    return accepted


def apply_aggregate_cap(
    decisions: list[SetupResult],
    open_trades: list[dict],
    balance: float,
    max_portfolio_risk_pct: float = 3.0,
    min_viable_pct: float = 0.25,
) -> list[SetupResult]:
    """Cap total open + new risk to a fraction of the account balance.

    Decisions are processed highest ``risk_pct`` first. A decision that
    would exceed the budget is either scaled down to the remaining
    headroom (if that's still viable) or dropped.
    """
    open_risk = sum(t.get("risk_amount", 0) for t in open_trades)
    budget = balance * (max_portfolio_risk_pct / 100)

    sorted_decisions = sorted(
        decisions, key=lambda d: d.extras.get("risk_pct", 0), reverse=True
    )

    accepted: list[SetupResult] = []
    for d in sorted_decisions:
        risk_pct = d.extras.get("risk_pct", 1.0)
        new_risk = balance * (risk_pct / 100)

        if open_risk + new_risk <= budget:
            accepted.append(d)
            open_risk += new_risk
            continue

        remaining = budget - open_risk
        remaining_pct = remaining / balance * 100
        if remaining_pct >= min_viable_pct:
            d.extras["risk_pct"] = remaining_pct
            accepted.append(d)
            open_risk = budget
        # else: drop - no viable budget remains

    return accepted


def daily_dd_breached(
    trades: list[dict],
    starting_balance: float,
    dd_pct: float = 3.0,
) -> bool:
    """Whether today's realized PnL has breached the daily drawdown limit."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    today_closed = [
        t
        for t in trades
        if t.get("status") == "CLOSED" and (t.get("exit_time") or "").startswith(today_str)
    ]

    today_pnl = sum(t.get("pnl", 0) or 0 for t in today_closed)

    return today_pnl <= -(starting_balance * dd_pct / 100)
