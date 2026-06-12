"""Historical backtest runner.

The backtest replays historical candles through your scanner, simulating
trades exactly like the live paper trader would. Useful for validating gate
logic before going live and for tuning parameters.

Usage:
    from model_trader.backtest import run_backtest
    run_backtest(scanner_class, config, days=7)

The scanner class must accept (config, data_adapter) and expose evaluate_at(ts).
See docs/backtest.md for details on implementing evaluate_at for your scanner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Callable, Any

from ..gates import SetupStatus, SetupResult


@dataclass
class BacktestTrade:
    timestamp: int
    symbol: str
    direction: str
    entry: float
    stop: float
    target: float
    outcome: str | None = None  # "WIN" | "LOSS" | "OPEN"
    pnl_r: float = 0.0
    exit_reason: str = ""


def run_backtest(
    scanner_factory: Callable[..., Any],
    config: dict,
    data_adapter,
    days: int = 7,
    step_timeframe: str = "5m",
    cooldown_bars: int = 6,
    evaluate_every_n_bars: int = 1,
) -> dict:
    """Replay history and simulate trades.

    If config contains an `ensemble:` section, runs in ensemble mode:
    N scanners vote on setups; the engine's weighted vote determines trades.

    Args:
        scanner_factory: Callable that returns a ScannerBase instance.
        config: Trader config dict (symbols, timeframes, optional ensemble section).
        data_adapter: DataAdapter instance for fetching historical candles.
        days: How many days of history to replay.
        step_timeframe: Candle timeframe to step through.
        cooldown_bars: Bars to wait after a trade closes before next entry.
        evaluate_every_n_bars: Only evaluate on every Nth bar.

    Returns:
        dict with per-symbol breakdown, overall metrics, and trade list.
    """
    if "ensemble" in config:
        return _run_backtest_ensemble(
            scanner_factory, config, data_adapter, days,
            step_timeframe, cooldown_bars, evaluate_every_n_bars,
        )

    return _run_backtest_single(
        scanner_factory, config, data_adapter, days,
        step_timeframe, cooldown_bars, evaluate_every_n_bars,
    )


def _run_backtest_single(
    scanner_factory, config, data_adapter, days,
    step_timeframe, cooldown_bars, evaluate_every_n_bars,
) -> dict:
    scanner = scanner_factory(config, data_adapter)
    all_trades: list[BacktestTrade] = []
    per_symbol: dict[str, dict] = {}

    for symbol in config.get("symbols", []):
        # Fetch all timeframes of historical data for this symbol
        hist: dict[str, list] = {}
        for tf in config.get("timeframes", ["1m", "5m", "15m", "1h", "4h"]):
            try:
                hist[tf] = data_adapter.fetch_historical(symbol, tf, days)
            except Exception as e:
                hist[tf] = []
                print(f"  [{symbol} {tf}] fetch failed: {e}")

        # Correlation data
        corr_hist: dict[str, list] = {}
        corr = config.get("correlations", {}).get(symbol)
        if corr:
            for tf in config.get("timeframes", []):
                try:
                    corr_hist[tf] = data_adapter.fetch_historical(corr, tf, days)
                except Exception:
                    corr_hist[tf] = []

        step_candles = hist.get(step_timeframe, [])
        if not step_candles:
            print(f"  [{symbol}] no {step_timeframe} data, skipping")
            continue

        trades_for_symbol: list[BacktestTrade] = []
        open_trade: BacktestTrade | None = None
        cooldown_until = 0

        for i in range(200, len(step_candles)):
            ts = step_candles[i]["timestamp"]

            # Check if open trade exited this bar
            if open_trade is not None:
                candle = step_candles[i]
                if open_trade.direction == "long":
                    if candle["low"] <= open_trade.stop:
                        open_trade.outcome = "LOSS"
                        open_trade.pnl_r = -1.0
                        open_trade.exit_reason = "SL"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars
                    elif candle["high"] >= open_trade.target:
                        open_trade.outcome = "WIN"
                        open_trade.pnl_r = round(
                            abs(open_trade.target - open_trade.entry) /
                            abs(open_trade.entry - open_trade.stop), 2
                        )
                        open_trade.exit_reason = "TP"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars
                else:
                    if candle["high"] >= open_trade.stop:
                        open_trade.outcome = "LOSS"
                        open_trade.pnl_r = -1.0
                        open_trade.exit_reason = "SL"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars
                    elif candle["low"] <= open_trade.target:
                        open_trade.outcome = "WIN"
                        open_trade.pnl_r = round(
                            abs(open_trade.entry - open_trade.target) /
                            abs(open_trade.entry - open_trade.stop), 2
                        )
                        open_trade.exit_reason = "TP"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars

                if open_trade is not None:
                    continue  # still in trade

            if i < cooldown_until:
                continue
            if i % evaluate_every_n_bars != 0:
                continue

            # Evaluate the scanner at this point in time
            try:
                result: SetupResult = scanner.evaluate_at(symbol, hist, corr_hist, ts)
            except AttributeError:
                raise RuntimeError(
                    "Your scanner must implement evaluate_at(symbol, hist, corr_hist, ts) "
                    "to support backtesting. See docs/backtest.md."
                )

            if result.status == SetupStatus.TAKE and result.entry and result.stop:
                open_trade = BacktestTrade(
                    timestamp=ts,
                    symbol=symbol,
                    direction=result.direction,
                    entry=result.entry,
                    stop=result.stop,
                    target=result.target,
                )

        if open_trade is not None:
            open_trade.outcome = "OPEN"
            trades_for_symbol.append(open_trade)

        all_trades.extend(trades_for_symbol)
        wins = sum(1 for t in trades_for_symbol if t.outcome == "WIN")
        losses = sum(1 for t in trades_for_symbol if t.outcome == "LOSS")
        per_symbol[symbol] = {
            "trades": len(trades_for_symbol),
            "wins": wins,
            "losses": losses,
            "total_r": sum(t.pnl_r for t in trades_for_symbol),
        }
        print(f"  {symbol}: {len(trades_for_symbol)} trades (W={wins} L={losses})")

    closed = [t for t in all_trades if t.outcome in ("WIN", "LOSS")]
    wins = [t for t in closed if t.outcome == "WIN"]
    losses = [t for t in closed if t.outcome == "LOSS"]
    total_r = sum(t.pnl_r for t in closed)
    win_pnl = sum(t.pnl_r for t in wins)
    loss_pnl = abs(sum(t.pnl_r for t in losses))

    return {
        "total_trades": len(all_trades),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_r": round(total_r, 2),
        "avg_r": round(total_r / len(closed), 2) if closed else 0,
        "profit_factor": round(win_pnl / loss_pnl, 2) if loss_pnl > 0 else float("inf"),
        "per_symbol": per_symbol,
        "trades": all_trades,
    }


def _run_backtest_ensemble(
    scanner_factory, config, data_adapter, days,
    step_timeframe, cooldown_bars, evaluate_every_n_bars,
) -> dict:
    """Backtest with ensemble voting: N scanners, weighted votes, per-scanner stats."""
    from ..ensemble import load_ensemble_config, EnsembleDB, EnsembleEngine

    ensemble_cfg = load_ensemble_config(config)
    db = EnsembleDB(ensemble_cfg.db_path)

    # Create scanners from ensemble config
    scanners = []
    for sd in ensemble_cfg.active_scanners:
        # Each scanner gets its own module/config
        scanner = scanner_factory(config, data_adapter)
        scanner._scanner_id = sd.id
        scanners.append(scanner)

    engine = EnsembleEngine(ensemble_cfg, db, scanners)

    all_trades: list[BacktestTrade] = []
    per_symbol: dict[str, dict] = {}
    per_scanner: dict[str, list] = {s._scanner_id: [] for s in scanners}

    for symbol in config.get("symbols", []):
        # Fetch historical data (shared across scanners)
        hist: dict[str, list] = {}
        for tf in config.get("timeframes", ["1m", "5m", "15m", "1h", "4h"]):
            try:
                hist[tf] = data_adapter.fetch_historical(symbol, tf, days)
            except Exception:
                hist[tf] = []

        step_candles = hist.get(step_timeframe, [])
        if not step_candles:
            continue

        trades_for_symbol: list[BacktestTrade] = []
        open_trade: BacktestTrade | None = None
        cooldown_until = 0

        # Pre-warm all scanners
        for s in scanners:
            for i in range(0, min(200, len(step_candles))):
                ts = step_candles[i]["timestamp"]
                try:
                    s.evaluate_at(symbol, hist, ts)
                except Exception:
                    pass

        for i in range(200, len(step_candles)):
            ts = step_candles[i]["timestamp"]

            # Check open trade exits (same as single mode)
            if open_trade is not None:
                candle = step_candles[i]
                if open_trade.direction == "long":
                    if candle["low"] <= open_trade.stop:
                        open_trade.outcome = "LOSS"
                        open_trade.pnl_r = -1.0
                        open_trade.exit_reason = "SL"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars
                    elif candle["high"] >= open_trade.target:
                        open_trade.outcome = "WIN"
                        open_trade.pnl_r = round(
                            abs(open_trade.target - open_trade.entry) /
                            abs(open_trade.entry - open_trade.stop), 2
                        )
                        open_trade.exit_reason = "TP"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars
                else:
                    if candle["high"] >= open_trade.stop:
                        open_trade.outcome = "LOSS"
                        open_trade.pnl_r = -1.0
                        open_trade.exit_reason = "SL"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars
                    elif candle["low"] <= open_trade.target:
                        open_trade.outcome = "WIN"
                        open_trade.pnl_r = round(
                            abs(open_trade.entry - open_trade.target) /
                            abs(open_trade.entry - open_trade.stop), 2
                        )
                        open_trade.exit_reason = "TP"
                        trades_for_symbol.append(open_trade)
                        open_trade = None
                        cooldown_until = i + cooldown_bars

            if open_trade is not None or i < cooldown_until:
                continue

            if (i - 200) % evaluate_every_n_bars != 0:
                continue

            # Ensemble evaluate: all scanners scan, engine votes
            all_results = []
            for s in scanners:
                try:
                    r = s.evaluate_at(symbol, hist, ts)
                    if r and r.status == SetupStatus.TAKE:
                        r.extras["scanner_id"] = s._scanner_id
                        all_results.append(r)
                except Exception:
                    continue

            if not all_results:
                continue

            decisions = engine.evaluate_all(all_results)
            if not decisions:
                continue

            d = decisions[0]
            if d.entry is None:
                continue

            trade = BacktestTrade(
                timestamp=ts,
                symbol=symbol,
                direction=d.direction or "long",
                entry=d.entry,
                stop=d.stop,
                target=d.target,
            )
            open_trade = trade

            # Record which scanner's vote won
            winner_id = d.extras.get("ensemble_scanner_id", "unknown")
            per_scanner[winner_id].append(trade)

        if open_trade is not None:
            open_trade.outcome = "OPEN"
            trades_for_symbol.append(open_trade)

        all_trades.extend(trades_for_symbol)
        wins = [t for t in trades_for_symbol if t.outcome == "WIN"]
        losses = [t for t in trades_for_symbol if t.outcome == "LOSS"]
        per_symbol[symbol] = {
            "trades": len(trades_for_symbol),
            "wins": len(wins),
            "losses": len(losses),
        }

    db.close()

    closed = [t for t in all_trades if t.outcome in ("WIN", "LOSS")]
    wins = [t for t in closed if t.outcome == "WIN"]
    losses = [t for t in closed if t.outcome == "LOSS"]
    total_r = sum(t.pnl_r for t in closed)
    win_pnl = sum(t.pnl_r for t in wins)
    loss_pnl = abs(sum(t.pnl_r for t in losses))

    result = {
        "total_trades": len(all_trades),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_r": round(total_r, 2),
        "avg_r": round(total_r / len(closed), 2) if closed else 0,
        "profit_factor": round(win_pnl / loss_pnl, 2) if loss_pnl > 0 else float("inf"),
        "per_symbol": per_symbol,
        "per_scanner": {
            sid: {
                "trades": len(ts),
                "wins": len([t for t in ts if t.outcome == "WIN"]),
                "losses": len([t for t in ts if t.outcome == "LOSS"]),
            }
            for sid, ts in per_scanner.items()
        },
        "trades": all_trades,
    }

    # Print per-scanner comparison
    print(f"\n  Ensemble backtest summary:")
    print(f"  Ensemble PF:   {result['profit_factor']}")
    for sid, stats in result["per_scanner"].items():
        if stats["trades"] > 0:
            print(f"  {sid:12s} {stats['trades']:3d} trades  "
                  f"W={stats['wins']} L={stats['losses']}")

    return result
