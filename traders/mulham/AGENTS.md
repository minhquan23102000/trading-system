<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# Mulham

## Purpose

HTF key-level + LTF confirmation scanner strategy extracted from 9 YouTube transcripts (~5 hours of video). Mulham is a 7-8 year forex trader and "Edge School" community founder who specializes in catching high-probability entries by waiting for price to reach pre-identified higher-timeframe (4H) key levels, then confirming on lower-timeframe (15m) patterns. The core philosophy: "Never chase; wait for price to come to your level." Backtested across BTC, ETH, SOL, and AVAX on Hyperliquid over 52 days with a 46.5% win rate and 1.80 profit factor.

## Key Files

| File | Description |
|------|-------------|
| `scanner.py` | 10-gate scanner pipeline; `Scanner` class implements `evaluate()` (live) and `evaluate_at()` (backtest) with mirrored gate logic using FVGDetector, SwingDetector, FailureSwingDetector, DisplacementDetector from framework |
| `config.yaml` | Symbols (BTC, ETH, SOL, AVAX), timeframes (1m–4h), paper trading settings (balance, per-trade %, max leverage) |
| `backtest.py` | Backtest entry point; runs `run_backtest()` with Scanner factory, 52-day lookback, 15m step timeframe (respects Hyperliquid's 5,000-candle API limit) |
| `main.py` | Live monitor entry point; instantiates Scanner, PaperTrader, and calls `run_monitor()` with 60-second scan interval |
| `strategy.md` | Full strategy breakdown: 4 core setups, key concepts (high probability ranges, price position, CCT, displacement, FVG respect), risk management (2:1 RR minimum), anti-patterns, voice/vocabulary |
| `philosophy_draft.md` | First-person reference in Mulham's voice; teaching methodology, edge school context, commentary on trader psychology |
| `transcripts/` | Source material: 9 YouTube transcripts (.txt and .en.vtt) that were analyzed to extract the strategy |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **Gate ordering:** gates are ordered by selectivity and trigger mode:
  - Gates 1–7 perform filtering logic; fail = SKIP (setup rejected)
  - Gate 8 (ENTRY_TRIGGER) has a special WAIT status: if the trigger is pending, keep the setup alive; once it fires or is disrespected, return SKIP or proceed
  - Gates 9–10 finalize the setup
- **Data depth constraint:** Hyperliquid's `candleSnapshot` API returns max 5,000 candles per timeframe:
  - 5m: ~17 days | 15m: ~52 days | 1h: ~208 days | 4h: ~833 days
  - Backtest steps on 15m to maximize lookback; Gate 8 still uses 5m for the trigger candle when available
  - Live paper trading (main.py) accumulates candles in memory after initial fetch — no API limit applies after the first load
- **Reason strings:** all gate failures and completions populate `result.reason` for the live dashboard journal. Use clear, specific language: e.g., "Outside kill zone (EST hour 11)" or "Stop < 0.20% of entry price" so traders understand why a setup was rejected
- **Direction logic:** direction is set in Gate 2 based on the nearest unfilled 4H FVG:
  - Bearish FVG → direction = "short"
  - Bullish FVG → direction = "long"
  - All downstream gates confirm or reject this direction; if rejected, setup is skipped

### Testing Requirements

Run backtest with:
```bash
cd traders/mulham && uv run python backtest.py
```

Expected output: per-symbol trade counts, win rates, total R, profit factor. Current baseline (as of last iteration):
- Total: 186 trades | Win rate: 46.5% | Net R: +79.5 | Profit factor: 1.80
- Per symbol: AVAX 51.2% WR (+24.9R), SOL 43.4% WR (+19.6R), BTC 45.8% WR (+18.0R), ETH 46.5% WR (+17.0R)

Run live monitor with:
```bash
cd traders/mulham && uv run python main.py
```

Produces a dashboard with live setups, `trades.json` journal, and paper trading stats. Verify:
- Scanner scans all 4 symbols every 60 seconds
- Only setups passing all 10 gates appear as TAKE in the journal
- Paper trading balance updates correctly based on win/loss trades

### Common Patterns

- **FVG detection and state management:** Code uses `FVGDetector().detect()` then `update_fvg_states()` to mark FVGs as "inversed" (filled by a closing candle) or "live" (unfilled). Always call `update_fvg_states()` after detection on fresh candles.
- **Swing detection for structure:** `SwingDetector` identifies higher/lower highs and lows; used to establish range anchoring and invalidation points for stops.
- **Failure-swing clusters:** `FailureSwingDetector` identifies sequences of swings that fail to break prior extremes (weakness pattern). Used in Gate 6 (WEAKNESS_STRENGTH).
- **Displacement filtering:** `DisplacementDetector` measures if a break of structure is ≥1.5x the prior leg size. Used to validate range breakouts (Gate 4) and strength candles (Gate 6).
- **Time filtering (kill zones):** Gate 1 checks EST hour (UTC-5, no DST correction) against `_KILL_ZONES` tuple list. Only Asia (20–24), London (2–5), and NY (7–10) hours pass.
- **Incremental history slicing:** `evaluate_at()` filters `hist` and `corr_hist` dicts by timestamp ≤ current evaluation time before running gates. Used during backtest to simulate real-time data arrival.

## Dependencies

### Internal

- `model_trader.gates.ScannerBase` — base class; defines `fetch_data()`, `fetch_correlation()`, interface
- `model_trader.gates.SetupResult, SetupStatus` — result envelope with fields: symbol, direction, entry, stop, target, reason, gates_passed, status (SKIP/WAIT/TAKE)
- `model_trader.detectors.SwingDetector` — identifies swings (higher highs/lows, lower highs/lows)
- `model_trader.detectors.FVGDetector` — detects 3-candle fair value gaps (imbalances)
- `model_trader.detectors.FailureSwingDetector` — clusters sequences of failing swings (weakness pattern)
- `model_trader.detectors.DisplacementDetector` — measures break-of-structure magnitude (BOS ≥ 1.5x rule)
- `model_trader.detectors.update_fvg_states()` — marks FVGs as inversed (filled) or live
- `model_trader.HyperliquidAdapter` — live and historical data source (candleSnapshot endpoint)
- `model_trader.PaperTrader` — simulates trades, tracks balance, computes R/loss, writes `trades.json` journal
- `model_trader.run_monitor()` — dashboard and monitoring loop
- `model_trader.backtest.run_backtest()` — backtest harness that evaluates scanner at each step, aggregates results

### External

- `yaml` — parses `config.yaml`
- Hyperliquid API (via `HyperliquidAdapter`) — 5m, 15m, 1h, 4h candleSnapshot endpoints (max 5,000 candles per timeframe)

## 10-Gate Pipeline Summary

| Gate | Name | Checks | Fail Action |
|------|------|--------|-------------|
| 1 | **KILL_ZONE** | Current EST hour in Asia (20–00), London (02–05), or NY (07–10) | SKIP |
| 2 | **HTF_KEY_LEVEL** | Unfilled 4H FVG exists; nearest one sets direction (long/short) | SKIP |
| 3 | **PRICE_POSITION** | Price at discount (≤50% range for longs) or premium (≥50% for shorts) to 15m range midpoint | SKIP |
| 4 | **HP_RANGE** | 15m range: displaced ≥1.5×, filled ≥50%, anchored to prior structure | SKIP |
| 5 | **DIRECTION_ALIGN** | 15m setup direction matches 4H candle bias (or price at 4H FVG level for reversals) | SKIP |
| 6 | **WEAKNESS_STRENGTH** | Failure-swing cluster (weakness) + 1.5x+ displacement (strength) in trade direction on 15m | SKIP |
| 7 | **FVG_RESPECT** | Direction-aligned 15m FVG: filled (retraced into it) but not inversed (candle body closed outside) | SKIP |
| 8 | **ENTRY_TRIGGER** | 5m candle closes outside FVG in trade direction (or 15m if 5m unavailable) | WAIT (if pending) / SKIP |
| 9 | **RR_OK** | Stop ≥0.20% of entry price; target ≥2:1 risk-reward | SKIP |
| 10 | **FINAL** | All gates pass; set direction, entry, stop, target; status = TAKE | — |

## Backtest Results

**Period:** 52 days | **Step TF:** 15m | **Data source:** Hyperliquid | **Symbols:** BTC, ETH, SOL, AVAX

| Symbol | Trades | Wins | Losses | Win Rate | Net R |
|--------|--------|------|--------|----------|-------|
| AVAX | 41 | 21 | 20 | 51.2% | +24.9 |
| SOL | 53 | 23 | 30 | 43.4% | +19.6 |
| BTC | 48 | 22 | 26 | 45.8% | +18.0 |
| ETH | 44 | 20 | 23 | 46.5% | +17.0 |
| **Total** | **186** | **86** | **99** | **46.5%** | **+79.5** |

**Aggregate metrics:** Profit factor: 1.80 | Avg R per trade: 0.43 | ~3.6 trades/day

### Iteration Log

| Iteration | Gate(s) | Change | Profit Factor | Win Rate | Total R |
|-----------|---------|--------|----------------|----------|---------|
| — | — | Original 10-gate pipeline, 4H min 30 candles | 0.80 | — | — |
| Fix | — | 4H min candles → 3; switched to 15m swings for analysis | 0.80 | — | — |
| 1 | 3 | Fib threshold: 38.2%/61.8% → 50% midpoint (OTE zone tightened) | 1.67 | 44.6% | +71.6 |
| 2 | 9 | Stop-distance floor: none → 0.15% of entry price | 1.74 | 45.5% | +76.6 |
| **3** | **9** | **Stop floor: 0.15% → 0.20% of entry price** | **1.80** | **46.5%** | **+79.5** |

**Iteration insights:**
- Iteration 1 unlocked the pipeline: the strategy's minimum fill is 50% per Mulham's stated rules; tighter Fibonacci zones were filtering out valid setups.
- Iterations 2–3 added a minimum stop-distance filter (0.20% of entry price), removing noise-width FVG setups where the gap is narrower than normal market volatility. ETH and BTC benefited most; AVAX flipped to positive win rate.

## Config.yaml Structure

```yaml
symbols:
  - "BTC"     # Scanning symbols
  - "ETH"
  - "SOL"
  - "AVAX"

timeframes:    # Candle fetch timeframes
  - 1m
  - 5m
  - 15m
  - 1h
  - 4h

correlations:  # Optional: correlation symbol pairs for divergence detection
  # "SYMBOL_A": "SYMBOL_B"  # Commented out; unused in current version

scan_interval_seconds: 60   # Live monitor polls every 60s

# Paper trading
paper_trading: true         # Enable/disable paper trading
paper_balance: 100000.0     # Starting balance ($)
per_trade_percent: 1.0      # Risk per trade (% of account)
max_leverage: 25            # Hyperliquid allows up to 20x; set conservatively

# Optional agent layer (unused)
agent_enabled: false
```

<!-- MANUAL: -->
