"""Walk-forward portfolio backtest across tradingnotes, znasdaq, and mulham.

Run from repo root:
    uv run python traders/portfolio_backtest.py

Output:
    - Per-trader standalone stats (30d)
    - Portfolio equity replay with look-ahead-safe composite sizing
    - Pairwise daily-return correlation between traders
    - Portfolio Sharpe / maxDD / PF vs standalone
"""

from __future__ import annotations

import importlib.util
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from model_trader import HyperliquidAdapter
from model_trader.backtest import run_backtest
from model_trader.portfolio.sizing import composite_from_journal, compute_weights


ROOT = Path(__file__).parent
DAYS = 30
STARTING_BALANCE = 10_000.0


def _load_scanner(trader_dir: Path):
    """Load Scanner class from a trader directory without requiring it to be a package."""
    spec = importlib.util.spec_from_file_location(
        f"_scanner_{trader_dir.name}",
        trader_dir / "scanner.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Scanner


def _load_cfg(name: str) -> dict:
    with open(ROOT / name / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def main() -> None:
    adapter = HyperliquidAdapter()

    traders = {
        "tradingnotes": (_load_scanner(ROOT / "tradingnotes"), _load_cfg("tradingnotes")),
        "znasdaq": (_load_scanner(ROOT / "znasdaq"), _load_cfg("znasdaq")),
        "mulham": (_load_scanner(ROOT / "mulham"), _load_cfg("mulham")),
    }

    # ── 1. Standalone backtests ──────────────────────────────────────────────
    standalone: dict[str, dict] = {}
    all_closed: list[tuple[int, str, object]] = []  # (ts_ms, trader_id, BacktestTrade)

    for tid, (Scanner, cfg) in traders.items():
        _sep(f"{tid.upper()} standalone ({DAYS}d)")
        result = run_backtest(
            scanner_factory=Scanner,
            config=cfg,
            data_adapter=adapter,
            days=DAYS,
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
            tid: composite_from_journal(pseudo, tid)
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

    # ── 3. Print standalone ───────────────────────────────────────────────────
    _sep("STANDALONE RESULTS")
    for tid, r in standalone.items():
        print(
            f"  {tid:15} | trades={r['total_trades']:3}  "
            f"WR={r['win_rate']:5.1f}%  PF={r['profit_factor']:5.2f}  "
            f"avgR={r['avg_r']:+.2f}  totalR={r['total_r']:+.2f}"
        )

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
