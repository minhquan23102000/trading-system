"""Historical backtest runner.

The backtest replays historical candles through your scanner, simulating
trades exactly like the live paper trader would. Useful for validating gate
logic before going live and for tuning parameters.

Usage:
    from model_trader.backtest import run_backtest
    run_backtest(scanner_class, config, days=7)

The scanner class must accept (config, data_adapter) and expose
evaluate_at(symbol, hist, corr_hist, ts). hist and corr_hist are already
sliced to ts by the runner — do not re-filter inside evaluate_at.
See docs/backtest.md for details on implementing evaluate_at.
"""
from __future__ import annotations

from collections import Counter

from dataclasses import dataclass
from typing import Callable, Any

from ..gates import SetupStatus, SetupResult
from ..logging import logger


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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _cost_in_r(entry: float, stop: float, cost_bps: float) -> float:
    """Round-trip transaction cost (fees+slippage+spread) expressed in R units.

    cost_bps is the ROUND-TRIP cost as basis points of notional. Per-unit risk
    is |entry - stop|; per-unit cost in price terms is entry * cost_bps/1e4.
    Cost in R = cost_price / risk. Returns 0.0 when risk or cost is non-positive
    (defensive: scanners already guard risk > 0).
    """
    risk = abs(entry - stop)
    if risk <= 0 or cost_bps <= 0:
        return 0.0
    return (entry * cost_bps / 1e4) / risk


def _fetch_data(
    data_adapter, symbol: str, timeframes: list[str], days: int, warn: bool = True
) -> dict[str, list]:
    """Fetch all timeframes for one symbol into a dict. Missing TFs → []."""
    result: dict[str, list] = {}
    for tf in timeframes:
        try:
            result[tf] = data_adapter.fetch_historical(symbol, tf, days)
        except Exception as e:
            result[tf] = []
            if warn:
                logger.warning(f"[{symbol} {tf}] fetch failed: {e}")
    return result


def _advance(ptr: dict[str, int], hist: dict[str, list], ts: int) -> None:
    """Advance each TF pointer to the first candle AFTER ts (in-place)."""
    for tf, candles in hist.items():
        p = ptr[tf]
        while p < len(candles) and candles[p]["timestamp"] <= ts:
            p += 1
        ptr[tf] = p


def _check_exit(
    candle: dict,
    trade: BacktestTrade,
    cost_bps: float,
    bar_idx: int,
    cooldown_bars: int,
) -> tuple[bool, int]:
    """Check if SL or TP was hit this bar. Mutates trade on hit.

    Returns (was_closed, new_cooldown_until). Both SL and TP hitting the same
    bar is resolved conservatively (SL wins — favour the loss).
    """
    cost = _cost_in_r(trade.entry, trade.stop, cost_bps)
    risk = abs(trade.entry - trade.stop)

    if trade.direction == "long":
        sl_hit = candle["low"] <= trade.stop
        tp_hit = candle["high"] >= trade.target
    else:
        sl_hit = candle["high"] >= trade.stop
        tp_hit = candle["low"] <= trade.target

    if sl_hit:
        trade.outcome = "LOSS"
        trade.pnl_r = round(-1.0 - cost, 2)
        trade.exit_reason = "SL"
        return True, bar_idx + cooldown_bars

    if tp_hit:
        trade.outcome = "WIN"
        trade.pnl_r = round(abs(trade.target - trade.entry) / risk - cost, 2)
        trade.exit_reason = "TP"
        return True, bar_idx + cooldown_bars

    return False, 0


def _aggregate(all_trades: list[BacktestTrade], per_symbol: dict, funnel: Counter | None = None) -> dict:
    """Build the standard results dict from a flat trade list."""
    closed = [t for t in all_trades if t.outcome in ("WIN", "LOSS")]
    wins   = [t for t in closed if t.outcome == "WIN"]
    losses = [t for t in closed if t.outcome == "LOSS"]
    total_r  = sum(t.pnl_r for t in closed)
    win_pnl  = sum(t.pnl_r for t in wins)
    loss_pnl = abs(sum(t.pnl_r for t in losses))
    return {
        "total_trades":  len(all_trades),
        "closed":        len(closed),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_r":       round(total_r, 2),
        "avg_r":         round(total_r / len(closed), 2) if closed else 0,
        "profit_factor": round(win_pnl / loss_pnl, 2) if loss_pnl > 0 else float("inf"),
        "per_symbol":    per_symbol,
        "gate_funnel":   dict(funnel) if funnel is not None else {},
        "trades":        all_trades,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

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
        evaluate_every_n_bars: Only evaluate on every Nth bar (counted from bar 200).

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


# ---------------------------------------------------------------------------
# Single-scanner backtest
# ---------------------------------------------------------------------------

def _run_backtest_single(
    scanner_factory, config, data_adapter, days,
    step_timeframe, cooldown_bars, evaluate_every_n_bars,
) -> dict:
    scanner = scanner_factory(config, data_adapter)
    cost_bps = float(config.get("backtest_cost_bps", 0.0))
    timeframes = config.get("timeframes", ["1m", "5m", "15m", "1h", "4h"])
    all_trades: list[BacktestTrade] = []
    per_symbol: dict[str, dict] = {}
    funnel: Counter = Counter()

    for symbol in config.get("symbols", []):
        hist = _fetch_data(data_adapter, symbol, timeframes, days)

        corr_hist: dict[str, list] = {}
        corr = (config.get("correlations") or {}).get(symbol)
        if corr:
            corr_hist = _fetch_data(data_adapter, corr, timeframes, days, warn=False)

        step_candles = hist.get(step_timeframe, [])
        if not step_candles:
            logger.warning(f"[{symbol}] no {step_timeframe} data, skipping")
            continue

        trades_for_symbol: list[BacktestTrade] = []
        open_trade: BacktestTrade | None = None
        cooldown_until = 0

        # Two-pointer: each TF pointer advances monotonically with ts,
        # so total pointer work is O(N_candles) across all bars — O(1) amortised.
        tf_ptr   = {tf: 0 for tf in hist}
        corr_ptr = {tf: 0 for tf in corr_hist}

        for i in range(200, len(step_candles)):
            ts = step_candles[i]["timestamp"]

            # Resolve open trade before evaluating new signals.
            if open_trade is not None:
                closed, new_cooldown = _check_exit(
                    step_candles[i], open_trade, cost_bps, i, cooldown_bars
                )
                if closed:
                    trades_for_symbol.append(open_trade)
                    open_trade = None
                    cooldown_until = new_cooldown
                else:
                    continue  # still in trade, skip signal evaluation

            if i < cooldown_until:
                continue
            if (i - 200) % evaluate_every_n_bars != 0:
                continue

            # Advance pointers and build sliced views only when evaluating.
            _advance(tf_ptr,   hist,      ts)
            _advance(corr_ptr, corr_hist, ts)
            hist_at = {tf: hist[tf][:tf_ptr[tf]]           for tf in hist}
            corr_at = {tf: corr_hist[tf][:corr_ptr[tf]]   for tf in corr_hist}

            try:
                result: SetupResult = scanner.evaluate_at(symbol, hist_at, corr_at, ts)
            except AttributeError:
                raise RuntimeError(
                    "Your scanner must implement evaluate_at(symbol, hist, corr_hist, ts). "
                    "See docs/backtest.md."
                )

            funnel[result.reason or result.status.name] += 1

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
        wins   = sum(1 for t in trades_for_symbol if t.outcome == "WIN")
        losses = sum(1 for t in trades_for_symbol if t.outcome == "LOSS")
        per_symbol[symbol] = {
            "trades":  len(trades_for_symbol),
            "wins":    wins,
            "losses":  losses,
            "total_r": sum(t.pnl_r for t in trades_for_symbol),
        }
        logger.info(f"{symbol}: {len(trades_for_symbol)} trades (W={wins} L={losses})")

    return _aggregate(all_trades, per_symbol, funnel)


# ---------------------------------------------------------------------------
# Ensemble backtest
# ---------------------------------------------------------------------------

def _run_backtest_ensemble(
    scanner_factory, config, data_adapter, days,
    step_timeframe, cooldown_bars, evaluate_every_n_bars,
) -> dict:
    """Backtest with ensemble voting: N scanners, weighted votes, per-scanner stats."""
    from ..ensemble import load_ensemble_config, EnsembleDB, EnsembleEngine

    ensemble_cfg = load_ensemble_config(config)
    db = EnsembleDB(ensemble_cfg.db_path)

    scanners = []
    for sd in ensemble_cfg.active_scanners:
        scanner = scanner_factory(config, data_adapter)
        scanner._scanner_id = sd.id
        scanners.append(scanner)

    engine   = EnsembleEngine(ensemble_cfg, db, scanners)
    cost_bps = float(config.get("backtest_cost_bps", 0.0))
    timeframes = config.get("timeframes", ["1m", "5m", "15m", "1h", "4h"])

    all_trades: list[BacktestTrade] = []
    per_symbol: dict[str, dict]     = {}
    per_scanner: dict[str, list]    = {s._scanner_id: [] for s in scanners}
    funnel: Counter = Counter()

    for symbol in config.get("symbols", []):
        hist = _fetch_data(data_adapter, symbol, timeframes, days, warn=False)

        corr_hist: dict[str, list] = {}
        corr = (config.get("correlations") or {}).get(symbol)
        if corr:
            corr_hist = _fetch_data(data_adapter, corr, timeframes, days, warn=False)

        step_candles = hist.get(step_timeframe, [])
        if not step_candles:
            continue

        trades_for_symbol: list[BacktestTrade] = []
        open_trade: BacktestTrade | None = None
        cooldown_until = 0

        tf_ptr   = {tf: 0 for tf in hist}
        corr_ptr = {tf: 0 for tf in corr_hist}

        for i in range(200, len(step_candles)):
            ts = step_candles[i]["timestamp"]

            if open_trade is not None:
                closed, new_cooldown = _check_exit(
                    step_candles[i], open_trade, cost_bps, i, cooldown_bars
                )
                if closed:
                    trades_for_symbol.append(open_trade)
                    open_trade = None
                    cooldown_until = new_cooldown
                else:
                    continue

            if i < cooldown_until:
                continue
            if (i - 200) % evaluate_every_n_bars != 0:
                continue

            _advance(tf_ptr,   hist,      ts)
            _advance(corr_ptr, corr_hist, ts)
            hist_at = {tf: hist[tf][:tf_ptr[tf]]         for tf in hist}
            corr_at = {tf: corr_hist[tf][:corr_ptr[tf]] for tf in corr_hist}

            all_results = []
            for s in scanners:
                try:
                    r = s.evaluate_at(symbol, hist_at, corr_at, ts)
                    funnel[r.reason or r.status.name] += 1
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

            open_trade = BacktestTrade(
                timestamp=ts,
                symbol=symbol,
                direction=d.direction or "long",
                entry=d.entry,
                stop=d.stop,
                target=d.target,
            )
            winner_id = d.extras.get("ensemble_scanner_id", "unknown")
            per_scanner[winner_id].append(open_trade)

        if open_trade is not None:
            open_trade.outcome = "OPEN"
            trades_for_symbol.append(open_trade)

        all_trades.extend(trades_for_symbol)
        wins   = [t for t in trades_for_symbol if t.outcome == "WIN"]
        losses = [t for t in trades_for_symbol if t.outcome == "LOSS"]
        per_symbol[symbol] = {
            "trades":  len(trades_for_symbol),
            "wins":    len(wins),
            "losses":  len(losses),
        }

    db.close()

    result = _aggregate(all_trades, per_symbol, funnel)
    result["per_scanner"] = {
        sid: {
            "trades":  len(ts),
            "wins":    sum(1 for t in ts if t.outcome == "WIN"),
            "losses":  sum(1 for t in ts if t.outcome == "LOSS"),
        }
        for sid, ts in per_scanner.items()
    }

    logger.info("Ensemble backtest summary:")
    logger.info(f"Ensemble PF:   {result['profit_factor']}")
    for sid, stats in result["per_scanner"].items():
        if stats["trades"] > 0:
            logger.info(f"  {sid:12s} {stats['trades']:3d} trades  "
                        f"W={stats['wins']} L={stats['losses']}")

    return result
