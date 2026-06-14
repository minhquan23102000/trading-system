"""Walk-forward portfolio backtest.

Reads traders/portfolio.yaml to discover which traders to backtest.
Add or remove a trader there — no code changes needed.

Run from repo root:
    uv run python traders/portfolio_backtest.py

Output:
    - Per-trader standalone stats (30d)
    - Portfolio equity replay with look-ahead-safe composite sizing
    - Pairwise daily-return correlation between traders
    - Portfolio Sharpe / maxDD / PF vs standalone
"""

from __future__ import annotations

import math
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))  # ensure traders/ is importable
from utils import load_cfg, load_scanner
from diagnostics import (
    print_funnel,
    print_stop_histogram,
    print_direction_breakdown,
    print_symbol_breakdown,
)

from model_trader import (
    BinanceAdapter,
    CachingDataAdapter,
    HyperliquidAdapter,
    YahooFinanceAdapter,
)
from model_trader.backtest import run_backtest
from model_trader.portfolio.sizing import composite_from_journal, compute_weights


ROOT = Path(__file__).parent
STARTING_BALANCE = 10_000.0
OOS_FRACTION = 0.30  # last 30% of each trader's trade timeline = out-of-sample

# Per-trader data source, lookback window, and step timeframe.
#
# mulham/tradingnotes (Binance, crypto): years of native history at every
# configured interval -> 180d on the scanner's natural step timeframe.
# znasdaq (Yahoo proxies): 1h/4h cover 180d; 5m/15m only cover the most
# recent ~60d (gates degrade gracefully on the older portion) -> 180d on 1h.
_YAHOO_SYMBOL_MAP = {
    "xyz:GOLD": "GC=F",
    "xyz:SP500": "^GSPC",
    "xyz:SILVER": "SI=F",
    "xyz:NVDA": "NVDA",
}


def _trader_data_config(name: str) -> tuple[object, int, str]:
    """Return (data_adapter, days, step_timeframe) for a trader."""
    cache_dir = ROOT / name / ".cache"
    if name == "znasdaq":
        return (
            CachingDataAdapter(YahooFinanceAdapter(symbol_map=_YAHOO_SYMBOL_MAP), cache_dir=cache_dir),
            180,
            "1h",
        )
    if name in ("mulham", "tradingnotes"):
        return (
            CachingDataAdapter(BinanceAdapter(), cache_dir=cache_dir),
            180,
            "5m",
        )
    # Fallback: legacy Hyperliquid path for any trader not yet migrated.
    return (HyperliquidAdapter(), 30, "5m")


def _sep(title: str = "") -> None:
    line = "=" * 60
    print(f"\n{line}")
    if title:
        print(f"  {title}")
        print(line)


def _bt_to_pseudo_journal(bt_trade, trader_id: str) -> dict:
    """Convert a BacktestTrade to a journal-compatible dict for composite computation."""
    return {
        "status": "CLOSED",
        "pnl": bt_trade.pnl_r,  # R as proxy; units cancel in PF ratio
        "risk_amount": 1.0,
        "exit_time": datetime.fromtimestamp(
            bt_trade.timestamp / 1000, tz=timezone.utc
        ).isoformat(),
        "extras": {"trader_id": trader_id},
    }


def _seg_metrics(trades) -> dict:
    """PF/WR/avgR for a list of BacktestTrades (closed only). Outcome-based PF,
    matching runner.py's definition."""
    closed = [t for t in trades if t.outcome in ("WIN", "LOSS")]
    if not closed:
        return {"n": 0, "wr": 0.0, "pf": 0.0, "avg_r": 0.0, "total_r": 0.0}
    wins = [t for t in closed if t.outcome == "WIN"]
    win_pnl = sum(t.pnl_r for t in wins)
    loss_pnl = abs(sum(t.pnl_r for t in closed if t.outcome == "LOSS"))
    total_r = sum(t.pnl_r for t in closed)
    return {
        "n": len(closed),
        "wr": len(wins) / len(closed) * 100,
        "pf": (win_pnl / loss_pnl) if loss_pnl > 0 else float("inf"),
        "avg_r": total_r / len(closed),
        "total_r": total_r,
    }


def _split_is_oos(trades, oos_frac: float = OOS_FRACTION):
    """Split closed trades by TIME into (in_sample, out_of_sample, cutoff_ts).
    Cutoff = min_ts + (max_ts - min_ts) * (1 - oos_frac) over this trader's own
    trade timeline. Returns (is_metrics, oos_metrics, cutoff_ts | None)."""
    closed = [t for t in trades if t.outcome in ("WIN", "LOSS")]
    if len(closed) < 2:
        return _seg_metrics(closed), _seg_metrics([]), None
    ts = sorted(t.timestamp for t in closed)
    lo, hi = ts[0], ts[-1]
    cutoff = lo + (hi - lo) * (1 - oos_frac)
    return (
        _seg_metrics([t for t in closed if t.timestamp < cutoff]),
        _seg_metrics([t for t in closed if t.timestamp >= cutoff]),
        cutoff,
    )


def main() -> None:
    with open(ROOT / "portfolio.yaml", encoding="utf-8") as f:
        pcfg = yaml.safe_load(f)

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

    traders = {
        name: (load_scanner(ROOT / name), load_cfg(ROOT / name))
        for name in trader_names
    }


    # ── 1. Standalone backtests ──────────────────────────────────────────────
    standalone: dict[str, dict] = {}
    all_closed: list[tuple[int, str, object]] = []  # (ts_ms, trader_id, BacktestTrade)

    for tid, (Scanner, cfg) in traders.items():
        data_adapter, days, step_timeframe = _trader_data_config(tid)
        _sep(f"{tid.upper()} standalone ({days}d)")
        result = run_backtest(
            scanner_factory=Scanner,
            config=cfg,
            data_adapter=data_adapter,
            days=days,
            step_timeframe=step_timeframe,
        )
        standalone[tid] = result
        for t in result["trades"]:
            if t.outcome in ("WIN", "LOSS"):
                all_closed.append((t.timestamp, tid, t))

    all_closed.sort(key=lambda x: x[0])

    # ── 2. Portfolio equity replay ────────────────────────────────────────────
    balance = STARTING_BALANCE
    equity: list[float] = [balance]
    portfolio_trades: list[dict] = []

    for entry_ts, trader_id, bt in all_closed:
        # Build pseudo-journal from trades CLOSED BEFORE this entry timestamp
        pseudo = [
            _bt_to_pseudo_journal(t2, t2_tid)
            for t2_ts, t2_tid, t2 in all_closed
            if t2_ts < entry_ts
        ]

        composites = {
            tid: composite_from_journal(
                pseudo, tid,
                seed_pf=seeds.get(tid, {}).get("pf", 0.0),
                seed_n=seeds.get(tid, {}).get("n", 0),
            )
            for tid in traders
        }
        weights = compute_weights(composites, base_pct=1.0, min_pct=0.25, max_pct=2.0)

        risk_pct = weights[trader_id]
        risk_dollar = balance * (risk_pct / 100)
        pnl_dollar = risk_dollar * bt.pnl_r

        balance += pnl_dollar
        equity.append(balance)
        portfolio_trades.append({
            "trader_id": trader_id,
            "symbol": bt.symbol,
            "outcome": bt.outcome,
            "r": bt.pnl_r,
            "risk_pct": risk_pct,
            "pnl": pnl_dollar,
            "balance": balance,
            "ts": entry_ts,
        })

    # ── 3. Print standalone + seed priors ────────────────────────────────────
    _sep("STANDALONE RESULTS")
    for tid, r in standalone.items():
        seed = seeds.get(tid, {})
        seed_str = (
            f"  seed=PF{seed['pf']:.2f}/n{seed['n']}"
            if seed.get("n", 0) >= 10 else "  no-seed"
        )
        print(
            f"  {tid:15} | trades={r['total_trades']:3}  "
            f"WR={r['win_rate']:5.1f}%  PF={r['profit_factor']:5.2f}  "
            f"avgR={r['avg_r']:+.2f}  totalR={r['total_r']:+.2f}"
            f"{seed_str}"
        )


    _sep("IN-SAMPLE / OUT-OF-SAMPLE  (OOS = last 30% of each trader's timeline)")
    for tid, r in standalone.items():
        is_m, oos_m, cutoff = _split_is_oos(r["trades"])
        cut = (
            datetime.fromtimestamp(cutoff / 1000, tz=timezone.utc).date().isoformat()
            if cutoff else "n/a"
        )
        print(f"  {tid:15} | OOS cutoff={cut}")
        print(f"    IS : n={is_m['n']:3}  WR={is_m['wr']:5.1f}%  "
              f"PF={is_m['pf']:5.2f}  avgR={is_m['avg_r']:+.2f}")
        print(f"    OOS: n={oos_m['n']:3}  WR={oos_m['wr']:5.1f}%  "
              f"PF={oos_m['pf']:5.2f}  avgR={oos_m['avg_r']:+.2f}")

    _sep("PER-TRADER DIAGNOSTICS")
    for tid, r in standalone.items():
        print(f"--- {tid} ---")
        print_funnel(r)
        print_stop_histogram(r["trades"])
        print_direction_breakdown(r["trades"])
        print_symbol_breakdown(r["trades"])
    # ── 4. Portfolio stats ────────────────────────────────────────────────────
    if not portfolio_trades:
        print("\nNo closed portfolio trades.")
        return

    wins = [t for t in portfolio_trades if t["outcome"] == "WIN"]
    losses = [t for t in portfolio_trades if t["outcome"] == "LOSS"]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    wr = len(wins) / len(portfolio_trades) * 100
    avg_r = sum(t["r"] for t in portfolio_trades) / len(portfolio_trades)
    total_pnl = balance - STARTING_BALANCE

    # Max drawdown
    peak = STARTING_BALANCE
    max_dd_pct = 0.0
    for bal in equity:
        peak = max(peak, bal)
        dd_pct = (peak - bal) / peak * 100
        max_dd_pct = max(max_dd_pct, dd_pct)

    # Worst standalone maxDD (for comparison)
    worst_standalone_dd = 0.0
    for tid, r in standalone.items():
        trades = [t for t in r["trades"] if t.outcome in ("WIN", "LOSS")]
        b = STARTING_BALANCE
        pk = STARTING_BALANCE
        mdd = 0.0
        for t in trades:
            b += b * 0.01 * t.pnl_r  # base 1% risk
            pk = max(pk, b)
            mdd = max(mdd, (pk - b) / pk * 100)
        worst_standalone_dd = max(worst_standalone_dd, mdd)

    # Daily Sharpe
    daily_pnl: dict[str, float] = defaultdict(float)
    for t in portfolio_trades:
        day = datetime.fromtimestamp(t["ts"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        daily_pnl[day] += t["pnl"]
    returns = list(daily_pnl.values())
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns))
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    _sep(f"PORTFOLIO ({len(portfolio_trades)} trades)")
    print(f"  WR={wr:.1f}%  PF={pf:.2f}  avgR={avg_r:+.2f}")
    print(f"  Total PnL=${total_pnl:+.2f}  ({STARTING_BALANCE:.0f} -> {balance:.2f})")
    print(f"  MaxDD={max_dd_pct:.1f}%  Sharpe={sharpe:.2f}")
    print(f"  Worst standalone MaxDD={worst_standalone_dd:.1f}%")

    # ── 5. Pairwise daily-return correlation ─────────────────────────────────
    _sep("PAIRWISE DAILY-RETURN CORRELATION")
    print("  (note: mulham & tradingnotes share BTC/ETH/SOL -- correlation expected high)")

    trader_daily: dict[str, dict[str, float]] = {tid: defaultdict(float) for tid in traders}
    for t in portfolio_trades:
        day = datetime.fromtimestamp(t["ts"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        trader_daily[t["trader_id"]][day] += t["pnl"]

    all_days = sorted({d for td in trader_daily.values() for d in td})
    tids = list(traders.keys())
    for i in range(len(tids)):
        for j in range(i + 1, len(tids)):
            a, b = tids[i], tids[j]
            va = [trader_daily[a].get(d, 0.0) for d in all_days]
            vb = [trader_daily[b].get(d, 0.0) for d in all_days]
            mean_a = sum(va) / len(va)
            mean_b = sum(vb) / len(vb)
            std_a = math.sqrt(sum((x - mean_a) ** 2 for x in va))
            std_b = math.sqrt(sum((y - mean_b) ** 2 for y in vb))
            if std_a > 0 and std_b > 0:
                num = sum((x - mean_a) * (y - mean_b) for x, y in zip(va, vb))
                corr = num / (std_a * std_b)
            else:
                corr = 0.0
            print(f"  {a:15} vs {b:15}:  {corr:+.3f}")


if __name__ == "__main__":
    main()
