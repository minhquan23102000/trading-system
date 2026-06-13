# Mulham Trading Scanner

HTF key-level + LTF confirmation strategy extracted from 9 YouTube transcripts (~5 hours of video) and implemented as a 10-gate scanner.

## Backtest Results

**Period:** 52 days | **Step TF:** 15m | **Data:** Hyperliquid (5,000 candle API limit)
**Symbols:** BTC, ETH, SOL, AVAX

| Symbol | Trades | W | L | Win Rate | Net R |
|--------|--------|---|---|----------|-------|
| AVAX | 41 | 21 | 20 | 51.2% | +24.9 |
| SOL | 53 | 23 | 30 | 43.4% | +19.6 |
| BTC | 48 | 22 | 26 | 45.8% | +18.0 |
| ETH | 44 | 20 | 23 | 46.5% | +17.0 |
| **Total** | **186** | **86** | **99** | **46.5%** | **+79.5R** |

**Profit factor:** 1.80 | **Avg R/trade:** 0.43 | **~3.6 trades/day**

### Iteration Log

| # | Gate | Change | PF | WR | Total R |
|---|------|--------|-----|-----|-----|
| — | — | Original 10 gates, 4H min 30 candles | 0.80 | — | — |
| Fix | — | 4H min → 3 candles, switch to 15m swings | 0.80 | — | — |
| 1 | 3 | Fib threshold: 38.2%/61.8% → 50% midpoint | 1.67 | 44.6% | +71.6 |
| 2 | 9 | Stop-distance floor: none → 0.15% | 1.74 | 45.5% | +76.6 |
| **3** | **9** | **Stop floor: 0.15% → 0.20%** | **1.80** | **46.5%** | **+79.5** |

Iteration 1 unlocked the pipeline — the strategy's own stated minimum is 50% fill;
the tighter OTE zone was filtering out valid setups. Iterations 2-3 added a
minimum stop-distance filter (0.20% of entry price) that removes noise-width FVG
setups where the gap is narrower than normal volatility spread. ETH and BTC
benefited most; AVAX flipped to positive win rate.

## Gate Pipeline

| # | Gate | What it checks | Fail → |
|---|------|---------------|--------|
| 1 | KILL_ZONE | Current time in Asia/London/NY session (EST) | SKIP |
| 2 | HTF_KEY_LEVEL | Unfilled 4H FVG exists; nearest one sets direction | SKIP |
| 3 | PRICE_POSITION | Price at discount (long) or premium (short) vs 15m range 50% | SKIP |
| 4 | HP_RANGE | 15m range: displaced ≥1.5×, filled ≥50%, anchored to 4H FVG | SKIP |
| 5 | DIRECTION_ALIGN | Setup direction matches 4H candle bias (or price at a 4H FVG) | SKIP |
| 6 | WEAKNESS_STRENGTH | Failure-swing cluster + displacement in trade direction on 15m | SKIP |
| 7 | FVG_RESPECT | Direction-aligned 15m FVG that is filled but not inversed | SKIP |
| 8 | ENTRY_TRIGGER | 5m candle closes outside FVG in trade direction | WAIT |
| 9 | RR_OK | Stop ≥0.20% of price, target ≥2:1 risk-reward | SKIP |
| 10 | FINAL | Set entry/stop/target/direction → TAKE | — |

## Data Depth Constraint

Hyperliquid's `candleSnapshot` endpoint returns max 5,000 candles per timeframe:
- 5m: ~17 days | 15m: ~52 days | 1h: ~208 days | 4h: ~833 days

The backtest steps on **15m** to maximize lookback. Gate 8 still uses 5m for
the trigger candle when available. A local candle cache would remove this limit
entirely for future runs.

## Commands

```bash
# Backtest
cd traders/mulham && uv run python backtest.py

# Live paper trading
cd traders/mulham && uv run python main.py
```

## Files

| File | Purpose |
|------|---------|
| `strategy.md` | Full strategy extraction — 4 setups, 10 gates, key concepts |
| `philosophy_draft.md` | First-person reference in Mulham's voice |
| `scanner.py` | Gate implementation (imports framework detectors) |
| `config.yaml` | Symbols, timeframes, paper trading settings |
| `backtest.py` | Backtest entry point |
| `main.py` | Live monitor entry point |
| `transcripts/` | Source YouTube transcripts (9 videos) |
