"""Pure diagnostic breakdowns over backtest results.

Consumed by portfolio_backtest.py's PER-TRADER DIAGNOSTICS section. Each
function takes the dict returned by run_backtest() (or the trade list) and
prints a small table to stdout. No state, no side effects beyond printing.
"""

from __future__ import annotations


def _closed(trades):
    return [t for t in trades if t.outcome in ("WIN", "LOSS")]


def _pf(trades) -> float:
    wins = [t for t in trades if t.outcome == "WIN"]
    losses = [t for t in trades if t.outcome == "LOSS"]
    win_pnl = sum(t.pnl_r for t in wins)
    loss_pnl = abs(sum(t.pnl_r for t in losses))
    return round(win_pnl / loss_pnl, 2) if loss_pnl > 0 else float("inf")


def _wr(trades) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.outcome == "WIN")
    return round(wins / len(trades) * 100, 1)


def _avg_r(trades) -> float:
    if not trades:
        return 0.0
    return round(sum(t.pnl_r for t in trades) / len(trades), 2)


def print_funnel(results: dict, top: int = 12) -> None:
    """Print the gate-rejection funnel, most common reason first."""
    funnel = results.get("gate_funnel", {})
    if not funnel:
        print("    (no gate funnel data)")
        return
    for reason, count in sorted(funnel.items(), key=lambda kv: kv[1], reverse=True)[:top]:
        print(f"    {count:6d}  {reason}")


def print_stop_histogram(trades) -> None:
    """Distribution of stop distance (% of entry) for closed trades."""
    closed = _closed(trades)
    if not closed:
        print("    (no closed trades)")
        return

    buckets = [
        ("<0.10%", 0.0, 0.0010),
        ("0.10-0.20%", 0.0010, 0.0020),
        ("0.20-0.30%", 0.0020, 0.0030),
        ("0.30-0.50%", 0.0030, 0.0050),
        ("0.50-1.0%", 0.0050, 0.0100),
        (">1.0%", 0.0100, float("inf")),
    ]
    pcts = sorted(abs(t.entry - t.stop) / t.entry for t in closed)
    for label, lo, hi in buckets:
        count = sum(1 for p in pcts if lo <= p < hi)
        print(f"    {label:>12}: {count:4d}")

    n = len(pcts)
    p50 = pcts[int(n * 0.50)] if n else 0.0
    p90 = pcts[min(int(n * 0.90), n - 1)] if n else 0.0
    print(f"    p50={p50*100:.2f}%  p90={p90*100:.2f}%")


def print_direction_breakdown(trades) -> None:
    """n/WR/PF/avgR split by trade direction."""
    closed = _closed(trades)
    if not closed:
        print("    (no closed trades)")
        return
    for direction in ("long", "short"):
        sub = [t for t in closed if t.direction == direction]
        if not sub:
            continue
        print(
            f"    {direction:6}: n={len(sub):3}  WR={_wr(sub):5.1f}%  "
            f"PF={_pf(sub):5.2f}  avgR={_avg_r(sub):+.2f}"
        )


def print_symbol_breakdown(trades) -> None:
    """n/WR/PF/avgR split by symbol."""
    closed = _closed(trades)
    if not closed:
        print("    (no closed trades)")
        return
    symbols = sorted({t.symbol for t in closed})
    for symbol in symbols:
        sub = [t for t in closed if t.symbol == symbol]
        print(
            f"    {symbol:8}: n={len(sub):3}  WR={_wr(sub):5.1f}%  "
            f"PF={_pf(sub):5.2f}  avgR={_avg_r(sub):+.2f}"
        )
