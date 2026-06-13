<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# monitor

## Purpose

The live trading loop. Implements the scan → filter → execute → dashboard cycle that runs continuously during a live trading session. Supports single-scanner mode (one scanner emitting signals) or ensemble voting mode (multiple scanners voting on decisions). The loop manages all timing, exit checks, duplicate/invalidated-level filtering, trade execution, and performance display.

## Key Files

| File | Description |
|------|-------------|
| `live.py` | `run_monitor()` loop — the entry point for live trading. Handles scan intervals, exit checks, filtering, trade execution, and dashboard rendering. Internal helpers `_build_dashboard()` and `_fmt_price()` format output. |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

The monitor module is the **top of the stack** (see `docs/architecture.md`). It does not export any classes — only the `run_monitor()` function. Do not add new public symbols here.

The loop follows a strict sequence every `scan_interval` seconds (or `fast_interval_when_open` if a trade is open):

1. **Exit check**: `paper_trader.check_exits()` — close trades that hit TP/SL using 1-minute candles.
2. **Scan**: Either `ensemble.scan_all()` (multi-scanner mode) or `scanner.scan_all()` (single-scanner mode).
3. **Dashboard**: Render all results (TAKE, WAIT, SKIP, NO_SETUP) to stdout, with scan time and performance metrics.
4. **Filter & execute**: For each TAKE result that passes both filters, call `paper_trader.execute()`.
5. **Summary**: Print open trades, closed trades this cycle, and rolling performance stats.
6. **Sleep**: Wait `scan_interval` seconds (or `fast_interval_when_open` if any trade is open).

The two filters are **always applied** (cannot be disabled):
- **`is_duplicate_setup()`** — block re-entry on identical entry/stop/target within `duplicate_lookback_min` (default 15 min).
- **`is_invalidated_level()`** — block re-entry at a price level that just got stopped out within `invalidated_level_hours` (default 6h) unless the new attempt is `invalidated_distance_pct` away (default 0.5% = 50 bps).

These filters exist because real scanners exhibit two failure modes: repeating the same signal bar (duplicates) and re-triggering on a level that just stopped out (cascades).

### Testing Requirements

No unit tests live in `tests/` for the monitor module itself — it is integration-only. The monitor is verified end-to-end by running `run_monitor()` with a real (or paper) scanner in `traders/<name>/main.py`. See `docs/pipeline.md` for the trader workflow.

### Common Patterns

- `run_monitor()` runs forever until `KeyboardInterrupt` (Ctrl+C).
- All parameters are optional except `scanner` and `paper_trader`.
- In single-scanner mode, the loop calls `scanner.scan_all()` and filters the results to only TAKE status for execution.
- In ensemble mode, the loop calls `ensemble.scan_all()` (which internally votes across multiple scanners) and executes the weighted decisions. The dashboard still shows all scanner results from `ensemble._scanners`, not just the final votes.
- The dashboard uses status prefixes (`>>>` for TAKE, `~` for WAIT, `x` for SKIP, and blank for NO_SETUP) and sorts results by status priority.
- Price formatting auto-scales decimal places based on magnitude (5 decimals for <10, 2 decimals for <1000, 1 decimal for ≥1000).

## Parameters & Configuration

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `scanner` | `ScannerBase` | Your scanner instance (single-scanner mode). Must have `symbols` attribute (list of strings) and `scan_all()` method. |
| `paper_trader` | `PaperTrader` | Journaled paper trader. Owns position state and the JSON journal (e.g., `traders/<name>/trades.json`). |

### Optional

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ensemble` | `EnsembleEngine \| None` | `None` | If provided, enables ensemble voting mode. Calls `ensemble.scan_all()` instead of `scanner.scan_all()`. Requires `ensemble/` module and YAML config. |
| `scan_interval` | `int` | `60` | Seconds between scans when idle (no open trades). |
| `fast_interval_when_open` | `int` | `15` | Seconds between scans when at least one trade is open. Allows faster exit checks. |
| `duplicate_lookback_min` | `int` | `15` | Lookback window (minutes) for duplicate setup detection. Blocks TAKE if an identical setup (same entry/stop/target) executed within this window. |
| `invalidated_level_hours` | `int` | `6` | Lookback window (hours) for invalidated level detection. Blocks TAKE if the stop level recently got hit and closed a trade. |
| `invalidated_distance_pct` | `float` | `0.5` | Minimum price distance (%) away from a recently-invalidated level to allow re-engagement. E.g., 0.5 = 50 basis points. |
| `title` | `str` | `"Model Trader Live Monitor"` | Header text shown in dashboard. Useful for distinguishing multiple monitors. |

## Loop Behavior

### Scan Phase

- **Single-scanner mode**: Calls `scanner.scan_all()`, which returns a list of `SetupResult` objects (one per symbol in `scanner.symbols`). The function filters these to extract only `TAKE` status results for execution.
- **Ensemble mode**: Calls `ensemble.scan_all()`, which internally iterates each registered scanner, collects votes, applies degradation checks, and returns a weighted-vote list. The dashboard shows all underlying scanner results (from `ensemble._scanners[*].last_results`) but execution filters from the ensemble's final decisions.

### Exit Phase

Before scanning, the monitor calls `paper_trader.check_exits()`, which:
- Fetches 1-minute candles for each open position's symbol.
- Checks whether price has hit the take-profit or stop-loss level.
- Closes the trade and returns the closed trade list.
- This step is idempotent (safe to call every iteration).

### Filter Phase (Pre-Execution)

For each TAKE result, the monitor applies two filters in order:

1. **Duplicate setup check**: If `is_duplicate_setup(journal_path, symbol, entry, stop, target, lookback_minutes)` returns `True`, skip this TAKE (do not execute).
2. **Invalidated level check**: If `is_invalidated_level(journal_path, symbol, direction, stop, current_price=entry, max_age_hours, required_distance_pct)` returns `True`, skip this TAKE.

Both filters query the paper trader's JSON journal to detect whether a similar setup was recently rejected.

### Execution Phase

For each TAKE that passes both filters:
- Call `paper_trader.execute(setup_result)`, which:
  - Creates a new trade record with the setup's entry/stop/target.
  - Appends it to the journal.
  - Returns the trade object (or `None` if execution failed).
- Print a confirmation message with trade ID, symbol, direction, price levels, and risk amount.

### Dashboard Phase

After scanning (regardless of whether any trades executed), render a formatted dashboard to stdout:
- **Header**: Title, UTC timestamp, scan duration.
- **Results**: Sorted by status (TAKE first, then WAIT, SKIP, NO_SETUP). For each result, show symbol, status, direction, gates passed, reason (for WAIT/SKIP), and price levels (for TAKE).
- **Open trades**: List all currently open positions with entry, stop, and target.
- **Closed this cycle**: Show any trades closed by exit checks, with PnL and R-multiple.
- **Performance**: If any trades have executed, show: win count, loss count, win rate (%), average R, profit factor, total PnL, max drawdown.

## Ensemble Integration

When `ensemble` is not `None`, the loop operates in **ensemble mode**:

- **Voting**: `ensemble.scan_all()` collects signals from all registered scanners, weights them, and returns a single decision list (one per symbol).
- **Degradation**: The ensemble engine automatically checks scanner correlation and performance degradation, potentially demoting underperforming scanners.
- **Database**: All voting results and performance scores are persisted to `ensemble.db` (SQLite) for scorer/challenger tracking.
- **Dashboard**: Displays all scanner results (not filtered to winners), so you can see the full vote distribution.

To use ensemble mode, you must:
1. Create an `EnsembleConfig` (YAML) with `scanners:` list, each defining a scanner class and its config.
2. Call `EnsembleEngine(config_path)` to load and initialize all scanners.
3. Pass the engine to `run_monitor(..., ensemble=engine)`.

See `docs/ensemble.md` for detailed ensemble design and configuration.

## Dependencies

### Internal

- `gates` — `SetupStatus` enum (NO_SETUP, SKIP, WAIT, TAKE).
- `paper_trader` — `PaperTrader` class, `is_duplicate_setup()`, `is_invalidated_level()`, `calculate_metrics()` functions.
- `ensemble` (optional) — `EnsembleEngine` for multi-scanner voting mode.

### External

- `time`, `datetime` — timing and formatting.

## State Management

- **State storage**: All persistent state is owned by `PaperTrader` (JSON journal) and optionally `EnsembleEngine` (SQLite database). The monitor loop itself is stateless—it recomputes all results every scan.
- **Journal path**: `paper_trader.journal_path` must point to a writable JSON file (typically `traders/<name>/trades.json`).
- **Ensemble database**: When using ensemble mode, the engine writes to `traders/<name>/ensemble.db` (SQLite).
- **Restart safety**: Both files survive restarts. On restart, the loop re-reads the journal and database to recover positions and history.

<!-- MANUAL: -->
