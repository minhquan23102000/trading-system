<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# znasdaq

## Purpose

Z Nasdaq is a draw-on-liquidity continuation trader targeting gold (XAUUSD, proxied as `xyz:GOLD`) and NASDAQ (NQ, proxied as `xyz:SP500`) across multiple timeframes. The strategy identifies untapped HTF draws confirmed by SMT divergence on correlated pairs, enters on LTF FVG taps or CISD breakers, and targets 1:1R with structural stops. The scanner implements a 6-gate pipeline and is tested via backtesting (7d/14d windows, 83–86% win rate, 5.0–6.33 profit factor) before live paper trading.

## Key Files

| File | Description |
|------|-------------|
| `scanner.py` | `Scanner(ScannerBase)` with 6-gate pipeline: HTF_BIAS, QUALIFIED_DOL, SMT_CONFIRM, ENTRY_ZONE, PROTECTED_STOP, FINAL. Uses SwingDetector, FVGDetector, FailureSwingDetector, CISDDetector, SMTDetector, DisplacementDetector. Entry points: `evaluate(symbol)` (live) and `evaluate_at(symbol, hist, corr_hist, ts)` (backtest). |
| `config.yaml` | Symbols, timeframes (5m/15m/1h/4h), correlations (GOLD↔SILVER, SP500↔NVDA), scan interval (60s), paper trading config (balance, per-trade %, leverage). |
| `main.py` | Live monitor entry point. Loads config, creates Scanner + HyperliquidAdapter + PaperTrader, calls `run_monitor()` with 60s scan interval. |
| `backtest.py` | Backtest entry point. Loads config, creates Scanner + HyperliquidAdapter, calls `run_backtest(scanner_factory=Scanner, days=7)`, prints results (trades, win rate, avg R, profit factor). |
| `README.md` | Strategy summary, gate pipeline table, symbols/timeframes, backtest results (7d: 19 trades, 83.3% WR, 0.67 avg R, 5.0 PF; 14d: 23 trades, 86.4% WR, 0.73 avg R, 6.33 PF), iteration log (no iterations needed). |
| `strategy.md` | Full strategy document: HTF draw on liquidity + SMT confirmation + 15m/5m entry + 1:1R target. |
| `philosophy_draft.md` | Trader voice and background. |

## Subdirectories

None. This directory is a self-contained trader project (transcripts/ and raw/ are gitignored).

## For AI Agents

### Working In This Directory

- The Scanner implements both **live** and **backtest** evaluation:
  - `evaluate(symbol)` fetches current candles via `data_adapter.fetch_candles(symbol, [candle_list])` and runs the gate pipeline.
  - `evaluate_at(symbol, hist, corr_hist, ts)` filters historical candles to the given timestamp (`ts`), then runs the same gate pipeline.
  - Both return `SetupResult` with `status` (WAIT/TAKE), `direction`, `entry`/`stop`/`target`, `gates_passed` list, and `reason`.

- **Detectors** are instantiated once in `__init__`:
  - `SwingDetector(lookback=2)`: High/low swings over 2 candles.
  - `FVGDetector()`: Fair value gaps. States (filled/unfilled/inversed/respected) tracked via `update_fvg_states()`.
  - `FailureSwingDetector(tolerance_pct=0.15)`: Swings that fail to break prior level by ≤15%.
  - `CISDDetector()`: Close Inside/Outside the Structure Day. CISD breakers detected via `detect_cisd_breaker()`.
  - `SMTDetector()`: Supply/Demand divergence on correlated pairs.
  - `DisplacementDetector(lookback=3, threshold_multiplier=1.5)`: 3-candle displacement at 1.5× threshold.

- **Gate order and logic**:
  1. **HTF_BIAS**: 4h displacement must exist and determine direction (bullish→long, bearish→short). Required minimum: 10 candles per timeframe (4h/1h/15m), ≥1 for 5m.
  2. **QUALIFIED_DOL**: Nearest untapped draw (failure-swing level, weak swing high/low, or unfilled 4h FVG) must exist in bias direction. Competing draw in opposite direction must be ≥1.2× farther away.
  3. **SMT_CONFIRM**: SMT signal of matching type (bullish for long, bearish for short) must be detected on 1h swings between primary and correlated symbol. Correlated symbol must have ≥10 1h candles.
  4. **ENTRY_ZONE**: 15m FVG of matching type (bullish for long, bearish for short) must be tapped with inversion/respect OR a CISD breaker of matching type must exist. Returns WAIT if neither condition is met.
  5. **PROTECTED_STOP**: Structural 4h swing on the invalidation side must exist. Stop price is the tightest of (structural swing, FVG boundary, breaker boundary) that is on the invalidation side, within ~2× the 15m ATR (14-candle average range).
  6. **FINAL**: Entry set to last 15m close. Risk = |entry − stop|. Target = entry ± risk. Status set to TAKE, reason = "All gates passed".

- **config.yaml keys**:
  - `symbols`: List of trading symbols (e.g., `"xyz:GOLD"`, `"xyz:SP500"`).
  - `timeframes`: List of candle timeframes (e.g., `[5m, 15m, 1h, 4h]`).
  - `correlations`: Dict mapping symbol → correlated symbol for SMT (e.g., `{"xyz:GOLD": "xyz:SILVER"}`).
  - `scan_interval_seconds`: Frequency of live scans (default 60).
  - `paper_trading`: Boolean; enable paper trading.
  - `paper_balance`: Starting balance for paper trader (default 100,000).
  - `per_trade_percent`: Risk per trade as % of balance (default 1.0).
  - `max_leverage`: Max leverage allowed (default 25).
  - `agent_enabled`: Boolean; enable optional ensemble agent layer (default false).

- **Wiring in main.py and backtest.py**:
  - Both load config via `yaml.safe_load()` from `config.yaml` in the same directory.
  - **main.py**: Creates `HyperliquidAdapter`, instantiates `Scanner(config, data)`, wraps in `PaperTrader(journal_path=trades.json, ...)`, calls `run_monitor(scanner=scanner, paper_trader=paper, scan_interval=60, title="znasdaq Live Monitor")`. The monitor runs `scanner.evaluate(symbol)` on each symbol every 60 seconds and logs trades to `trades.json`.
  - **backtest.py**: Creates `HyperliquidAdapter`, instantiates `Scanner(config, data)`, calls `run_backtest(scanner_factory=Scanner, config=config, data_adapter=data, days=7)`. The backtest harness iterates over historical data, calls `scanner.evaluate_at(symbol, hist, corr_hist, ts)` for each timestamp and symbol, accumulates results (win/loss, R values, profit factor), and prints summary.

### Testing Requirements

- **Unit test entry point**: `cd traders/znasdaq && uv run python backtest.py`
  - Backtests the Scanner against 7 days of Hyperliquid historical data (configurable via `days=` parameter).
  - Validates all six gates and ensures entry/stop/target prices are computed correctly.
  - Prints trade counts, win rate, average R, and profit factor.
  - Expected results: >50 trades (for statistical confidence), >70% win rate, profit factor >1.3.
  
- **Live validation**: `cd traders/znasdaq && uv run python main.py`
  - Runs the Scanner live against `xyz:GOLD` and `xyz:SP500` on Hyperliquid.
  - Simulates trades in PaperTrader, logs to `trades.json`.
  - Monitor dashboard shows each scan result, gates passed, and pending/closed trades.
  - No assertions; manual review of trades and gates passed per trade.

### Common Patterns

- **Detector initialization**: All detectors are created once in `__init__` with fixed hyperparameters (e.g., `SwingDetector(lookback=2)`). No dynamic re-tuning during evaluation.
- **Candle slicing for backtest**: `evaluate_at()` pre-filters candles to timestamps ≤ `ts` before passing to `_run_gates()`. This ensures the backtest does not use future data.
- **Draw on Liquidity candidates** (see `_nearest_draw()` helper):
  - Failure swings (level, direction).
  - Most recent un-swept swing high (long) or low (short).
  - Unfilled 4h FVGs (bullish for long, bearish for short).
  - Nearest candidate (smallest distance from current price) is selected; competitor in opposite direction must be ≥1.2× farther.
- **Entry price**: Always last 15m close (`c15m[-1]["close"]`), not the FVG tap or CISD level.
- **Reason strings**: Each gate appends a reason string to `result.reason` if it fails, enabling dashboard debugging and journal entries.
- **Status enum**: `SetupStatus.WAIT` means entry zone not yet reached (no tapped FVG or CISD breaker); `SetupStatus.TAKE` means all gates passed and setup is ready to trade.

## Dependencies

### Internal

- `model_trader.gates`: `ScannerBase`, `SetupResult`, `SetupStatus` base classes and enums.
- `model_trader.detectors`: `SwingDetector`, `FVGDetector`, `FailureSwingDetector`, `CISDDetector`, `SMTDetector`, `DisplacementDetector`, `update_fvg_states()`, `detect_cisd_breaker()` detection utilities.
- `model_trader`: `HyperliquidAdapter` (data fetching), `PaperTrader` (trade simulation), `run_monitor()` (live dashboard), `run_backtest()` (historical evaluation harness).

### External

- `yaml`: Config file parsing (PyYAML).
- Hyperliquid API (via HyperliquidAdapter): Real-time and historical candle data, trades.

<!-- MANUAL: -->
