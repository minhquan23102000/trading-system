# Mulham Trading Scanner

HTF key-level + LTF confirmation strategy extracted from 9 YouTube transcripts (~5 hours of video)
and implemented as a 10-gate scanner.

## Backtest Results

### Cost-adjusted baseline (current)

**Period:** 180d | **Step TF:** 5m | **Data:** Binance spot (`CachingDataAdapter`) | **Cost model:** 10bps round-trip

| Symbol | Trades | W | L | Win Rate |
|--------|--------|---|---|----------|
| BTC | 193 | 59 | 133 | 30.6% |
| ETH | 140 | 55 | 84 | 39.3% |
| SOL | 193 | 62 | 131 | 32.1% |
| AVAX | 160 | 54 | 106 | 33.8% |
| **Total** | **686** | **230** | **454** | **33.6%** |

**Profit factor:** 0.79 | **Avg R/trade:** −0.17 | **Total R:** −114.59 | **~3.8 trades/day**

> **Why costs matter so much here:** gate 9 enforces a 0.20% minimum stop distance.
> At 10bps round-trip, `_cost_in_r(entry, 0.20%-stop) = 0.5R` — half a full R wiped per trade
> just in friction. A strategy operating near 33% WR needs costs near zero to survive.

### IS / OOS split (70% / 30% time)

| Segment | Cutoff | n | WR | PF | avgR |
|---------|--------|---|----|----|------|
| In-sample | — | 478 | 32.2% | 0.74 | −0.21 |
| Out-of-sample | 2026-04-21 | 206 | 36.9% | 0.92 | −0.06 |

OOS is marginally less negative than IS — not evidence of edge, but no cliff either.
Both halves are sub-1.0 PF after cost.

### Frictionless baseline (superseded — kept for reference only)

| Symbol | Trades | W | L | Win Rate | Net R (no cost) |
|--------|--------|---|---|----------|-----------------|
| BTC | 193 | 59 | 133 | 30.6% | −6.41 |
| ETH | 140 | 55 | 84 | 39.3% | +27.42 |
| SOL | 193 | 62 | 131 | 32.1% | −2.54 |
| AVAX | 160 | 54 | 106 | 33.8% | +4.31 |
| **Total** | **686** | **230** | **454** | **33.6%** | **+22.78** |

**Frictionless PF:** 1.05 | **Frictionless avgR:** +0.03

The frictionless read was near-breakeven already. The 0.5R/trade floor cost converts
that thin positive edge into consistent loss.

### Prior result: 52d / 15m / Hyperliquid (legacy — different data source and timeframe)

| Symbol | Trades | W | L | Win Rate | Net R (no cost) |
|--------|--------|---|---|----------|-----------------|
| AVAX | 41 | 21 | 20 | 51.2% | +24.9 |
| SOL | 53 | 23 | 30 | 43.4% | +19.6 |
| BTC | 48 | 22 | 26 | 45.8% | +18.0 |
| ETH | 44 | 20 | 23 | 46.5% | +17.0 |
| **Total** | **186** | **86** | **99** | **46.5%** | **+79.5** |

**Frictionless PF:** 1.80 | **Frictionless avgR:** +0.43

This window's 46.5% WR vs 33.6% on the 180d run is a major discrepancy — the shorter
window caught a favorable regime or the Hyperliquid feed and 15m step interact differently
with the gates. Do not use this as a seed prior.

### Iteration Log

| # | Gate | Change | PF | WR | Total R |
|---|------|--------|-----|-----|-----|
| — | — | Original 10 gates, 4H min 30 candles | 0.80 | — | — |
| Fix | — | 4H min → 3 candles, switch to 15m swings | 0.80 | — | — |
| 1 | 3 | Fib threshold: 38.2%/61.8% → 50% midpoint | 1.67 | 44.6% | +71.6 |
| 2 | 9 | Stop-distance floor: none → 0.15% | 1.74 | 45.5% | +76.6 |
| **3** | **9** | **Stop floor: 0.15% → 0.20%** | **1.80** | **46.5%** | **+79.5** |

All iterations above were run on the **52d / 15m / Hyperliquid** frictionless window.
They do not carry over to the current 180d / 5m / Binance cost-adjusted baseline.

## Known Defects

| Defect | Location | Effect |
|--------|----------|--------|
| Degenerate range | Gate 4 HP_RANGE | `range_high`/`range_low` drawn from latest swing high and latest swing low independently — they need not form a coherent pair, producing a range that has no relationship to the actual displaced HP structure |
| 0.20% stop floor vs 10bps cost | Gate 9 + cost model | At the floor, cost = 0.5R/trade; the floor was calibrated frictionlessly on the 52d window |

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

## Data Source & Depth

Backtest uses `BinanceAdapter` (BTC/ETH/SOL/AVAX vs USDT) wrapped in
`CachingDataAdapter` (`.cache/`, gitignored) — years of native history at every
configured interval (1m/5m/15m/1h/4h). Live paper trading (`main.py`) uses
`HyperliquidAdapter` — unaffected by backtest changes.

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
| `config.yaml` | Symbols, timeframes, cost model, paper trading settings |
| `backtest.py` | Backtest entry point |
| `main.py` | Live monitor entry point |
| `transcripts/` | Source YouTube transcripts (9 videos) |
