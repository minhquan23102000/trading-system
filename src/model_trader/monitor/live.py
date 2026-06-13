"""Live monitor loop.

Scans symbols, shows a dashboard, opens paper trades on TAKE signals.
Supports single-scanner mode (default) and ensemble voting mode.

Call `run_monitor(scanner, paper_trader, ensemble=None)` to start.
"""


from __future__ import annotations

import time
from datetime import datetime, timezone

from ..gates import SetupStatus
from ..logging import logger
from ..trading import (
    PaperTrader,
    is_duplicate_setup,
    is_invalidated_level,
    calculate_metrics,
)


STATUS_PREFIX = {
    "TAKE": ">>> ",
    "WAIT": " ~  ",
    "SKIP": " x  ",
    "NO_SETUP": "    ",
}


def _fmt_price(price: float) -> str:
    """Auto-scale decimal places by price magnitude."""
    if price < 10:
        return f"{price:.5f}"
    if price < 1000:
        return f"{price:.2f}"
    return f"{price:.1f}"


def _build_dashboard(results: list, scan_time: float, title: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("=" * 105)
    lines.append(f"  {title}  |  {now} UTC  |  scan: {scan_time:.1f}s")
    lines.append("=" * 105)

    order = {"TAKE": 0, "WAIT": 1, "SKIP": 2, "NO_SETUP": 3}
    results = sorted(results, key=lambda r: order.get(r.status.value, 4))

    for r in results:
        prefix = STATUS_PREFIX.get(r.status.value, "    ")
        direction = (r.direction or "-").upper()
        lines.append(f"{prefix}{r.symbol:<15s} [{r.status.value:<8s}]  dir={direction}")

        if r.gates_passed:
            lines.append(f"      gates: {' -> '.join(r.gates_passed)}")
        if r.status != SetupStatus.TAKE and r.reason:
            lines.append(f"      reason: {r.reason}")
        if r.status == SetupStatus.TAKE:
            lines.append(
                f"      entry={_fmt_price(r.entry)}  "
                f"stop={_fmt_price(r.stop)}  "
                f"target={_fmt_price(r.target)}"
            )

        lines.append("")

    lines.append("=" * 105)
    return "\n".join(lines)


def run_monitor(
    scanner,
    paper_trader: PaperTrader,
    ensemble=None,
    portfolio=None,
    scan_interval: int = 60,
    fast_interval_when_open: int = 15,
    duplicate_lookback_min: int = 15,
    invalidated_level_hours: int = 6,
    invalidated_distance_pct: float = 0.5,
    title: str = "Model Trader Live Monitor",
) -> None:
    """Run the live scan-and-trade loop.

    Args:
        scanner: Your ScannerBase subclass instance (single-scanner mode).
        paper_trader: A PaperTrader instance (journal path + balance config).
        ensemble: Optional EnsembleEngine instance for multi-scanner voting.
        portfolio: Optional PortfolioOrchestrator instance. When set, scanner
            must be None. Takes precedence over ensemble.
        scan_interval: Seconds between scans when idle.
        fast_interval_when_open: Seconds between scans when a trade is open.
        duplicate_lookback_min: Minutes to block re-entry on identical setup.
        invalidated_level_hours: Hours after SL hit to block same-level re-entry.
        invalidated_distance_pct: Price distance (%) required for re-engagement.
        title: Header shown in dashboard.
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  {title}")
    if portfolio:
        n_sym = sum(len(s.symbols) for s in portfolio.scanners.values())
        logger.info(f"  Scanning {n_sym} symbols across {len(portfolio.scanners)} traders every {scan_interval}s")
    else:
        logger.info(f"  Scanning {len(scanner.symbols)} symbols every {scan_interval}s")
    mode = "Portfolio" if portfolio else ("Ensemble" if ensemble else "Single-scanner")
    logger.info(f"  Mode: {mode}")
    logger.info("  Press Ctrl+C to stop")
    logger.info("=" * 60)
    logger.info("Running first scan...")

    try:
        while True:
            t0 = time.time()

            # Close any hit stops/targets on open trades
            closed_this_cycle = paper_trader.check_exits()

            # Evaluate setups: ensemble mode or single-scanner mode
            try:
                if portfolio:
                    decisions = portfolio.scan_cycle()
                    results = portfolio.last_results
                elif ensemble:
                    decisions = ensemble.scan_all()
                    # Build dashboard from scanner results (not just decisions)
                    results = [
                        r
                        for s in ensemble._scanners
                        for r in s.last_results
                    ]
                else:
                    results = scanner.scan_all()
                    decisions = [r for r in results if r.status == SetupStatus.TAKE]
            except Exception as e:
                logger.error(f"Scan error: {e}")
                time.sleep(scan_interval)
                continue

            scan_time = time.time() - t0
            logger.info("\n" + _build_dashboard(results, scan_time, title))

            # Execute valid TAKE decisions
            open_symbols = {t["symbol"] for t in paper_trader.get_open_trades()}
            for r in decisions:
                if r.symbol in open_symbols:
                    continue
                if r.entry is None:
                    continue

                # Filter: duplicate
                if is_duplicate_setup(
                    paper_trader.journal_path,
                    r.symbol, r.entry, r.stop, r.target,
                    lookback_minutes=duplicate_lookback_min,
                ):
                    continue

                # Filter: invalidated level
                if is_invalidated_level(
                    paper_trader.journal_path,
                    r.symbol, r.direction, r.stop,
                    current_price=r.entry,
                    max_age_hours=invalidated_level_hours,
                    required_distance_pct=invalidated_distance_pct,
                ):
                    continue

                trade = paper_trader.execute(r)
                if trade:
                    logger.success(
                        f"  >> NEW TRADE: [{trade.id}] {trade.symbol} "
                        f"{trade.direction.upper()}  "
                        f"entry={_fmt_price(trade.entry_price)}  "
                        f"sl={_fmt_price(trade.stop_loss)}  "
                        f"tp={_fmt_price(trade.take_profit)}  "
                        f"risk=${trade.risk_amount:.2f}"
                    )

            # Summary
            open_trades = paper_trader.get_open_trades()
            if open_trades:
                lines = [f"\n  OPEN ({len(open_trades)})"]
                for t in open_trades:
                    lines.append(
                        f"  [{t['id']}] {t['symbol']} {t['direction'].upper()}  "
                        f"entry={_fmt_price(t['entry_price'])}  "
                        f"sl={_fmt_price(t['stop_loss'])}  "
                        f"tp={_fmt_price(t['take_profit'])}"
                    )
                logger.info("\n".join(lines))

            if closed_this_cycle:
                lines = ["\n  CLOSED THIS CYCLE"]
                for t in closed_this_cycle:
                    pnl = t.get("pnl", 0)
                    sign = "+" if pnl >= 0 else ""
                    lines.append(
                        f"  [{t['id']}] {t['symbol']} {t.get('outcome', '?')}  "
                        f"{sign}${pnl:.2f}  R={t.get('r_multiple', 0):.2f}"
                    )
                logger.info("\n".join(lines))

            m = calculate_metrics(paper_trader.journal_path)
            if m["total_trades"] > 0:
                logger.info(
                    f"\n  PERF | trades={m['total_trades']}  "
                    f"W/L={m['wins']}/{m['losses']}  "
                    f"WR={m['win_rate']}%  "
                    f"avgR={m['avg_rr']}  "
                    f"PF={m['profit_factor']}  "
                    f"PnL=${m['total_pnl']:.2f}  "
                    f"maxDD=${m['max_drawdown']:.2f}"
                )

            wait = fast_interval_when_open if open_trades else scan_interval
            logger.info(f"\nNext scan in {wait}s...\n")
            time.sleep(wait)

    except KeyboardInterrupt:
        logger.info("\nMonitor stopped.")
