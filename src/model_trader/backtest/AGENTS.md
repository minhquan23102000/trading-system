<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# backtest

## Purpose

Historical backtesting runner that replays past candles through a scanner, simulating trades with the same SL/TP logic as the live paper trader. Used to validate gate logic before going live and to measure strategy performance metrics (win rate, profit factor, average R).

## Key Files

| File | Description |
|------|-------------|
| `runner.py` | Contains `run_backtest(scanner_factory, config, data_adapter, days=7, ...)` — the main entry point that walks historical candles and simulates trades; includes `_run_backtest_single` (single scanner) and `_run_backtest_ensemble` (ensemble voting mode) |
| `__init__.py` | Public API — re-exports `run_backtest` |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **`scanner_factory` usage**: `run_backtest` expects a callable (usually a `Scanner` class) that accepts `(config, data_adapter)` and returns a scanner instance. The scanner must implement `evaluate_at(symbol, hist, corr_hist, ts)` — failure to implement this will raise `RuntimeError` at runtime.
- **Historical candle walking**: The runner fetches full history for all configured symbols and timeframes, then steps through the `step_timeframe` (default "5m") bar by bar starting at index 200. This ensures sufficient lookback data (200 bars) before evaluating any setups.
- **`evaluate_at()` contract**: Your scanner's `evaluate_at` method receives:
  - `symbol`: The symbol being evaluated
  - `hist`: `{timeframe: list[Candle]}` — full historical candles for the symbol. Your `evaluate_at` must filter by timestamp (`timestamp <= ts`) to avoid lookahead bias
  - `corr_hist`: Same shape as `hist`, for the correlation symbol (if configured)
  - `ts`: Current bar timestamp in milliseconds
  
  The method must return a `SetupResult` with the same semantics as live `evaluate()`.
- **Trade simulation**: At each bar, the runner:
  1. Checks if an open trade's SL or TP was hit (high/low of current bar)
  2. If no trade open and not in cooldown: calls `evaluate_at()`
  3. If result is `TAKE`, opens a trade at entry/stop/target
  4. After a trade closes: skips `cooldown_bars` before evaluating again
  
  Both SL and TP hitting in the same bar is resolved conservatively (favor the loss).
- **Ensemble mode**: If `config` contains an `ensemble:` section, `run_backtest` delegates to `_run_backtest_ensemble`, which runs N scanners and uses weighted voting to determine trades. Single-scanner mode uses `_run_backtest_single`.

### Testing Requirements

- No dedicated test file for backtest itself (integration testing via trader projects).
- Verify backtest runs end-to-end: `uv run python -m traders.<name>.backtest` (or call `run_backtest` directly in a test).
- Check that output includes per-symbol trade counts, win rate, profit factor, and total R — these validate simulation correctness.

### Common Patterns

- **Factoring gates**: The cleanest pattern is to extract your gate logic into a private `_run_gates(symbol, data, corr_data, ts)` method, then call it from both `evaluate()` (with live data) and `evaluate_at()` (with historical data). Your `evaluate_at` filters the passed-in dicts by timestamp, then delegates to `_run_gates`.
- **Avoiding lookahead bias**: Default to working with the most recent allowed candle (`data["5m"][-1]`) and slicing backward from there. Never access `data[timeframe][i+1]` or any future candle.
- **Candle structure**: Each candle is a dict with `{"timestamp", "open", "high", "low", "close", "volume"}`.

## Dependencies

### Internal

- `model_trader.gates` — `ScannerBase`, `SetupResult`, `SetupStatus`
- Any data adapter passed to `run_backtest` (typically `HyperliquidAdapter` from `model_trader.data`)

### External

- None (uses only standard library and imports from model_trader)

<!-- MANUAL: -->
