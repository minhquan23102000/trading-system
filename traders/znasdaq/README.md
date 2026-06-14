# Z Nasdaq — Trader Profile

## Overview
Prop firm trader. Primary: gold (XAUUSD) Asia session. Secondary: NASDAQ (NQ)
premarket/NY. Strategy: Draw on Liquidity continuation model, 1:1R target,
high win rate over high R:R. Trades SMT divergence + FVG entry + failure swing draws.

## Strategy Summary
1. Identify HTF draw on liquidity (failure swings > weak highs/lows > unfilled
   HTF FVG) on 4h/1h with displacement pointing toward it.
2. Confirm with SMT divergence between correlated pairs at the recent swing.
3. Wait for 15m/5m FVG tap + inversion or CISD breaker as entry trigger.
4. Protected stop at structural invalidation (swing extreme or gap boundary).
5. Target 1R. Done.

## Gate Pipeline

| Gate | Check | Pass Condition |
|------|-------|----------------|
| 1 | HTF Structure & Bias | 4h swing + displacement toward un-tapped draw |
| 2 | Qualified Draw on Liquidity | Failure swings OR weak H/L OR unfilled HTF FVG; no competing draw |
| 3 | SMT Confirmation | SMT detected on correlated pair at recent swing |
| 4 | Entry Zone Reached | 15m/5m FVG tapped + inversion or CISD breaker |
| 5 | Protected Stop Exists | Clear structural invalidation point within reason |
| 6 | Compute Levels | Entry/stop/target/direction set → TAKE |

## Symbols & Timeframes
- Primary: `xyz:GOLD` (Hyperliquid proxy for XAUUSD), `xyz:SP500` (NQ proxy)
- Correlation pairs: `xyz:SILVER` (gold SMT), `xyz:NVDA` (index SMT)
- Context: 4h, 1h
- Entry: 15m, 5m

## Backtest Results

### Cost-adjusted baseline (current)

**Data source:** Yahoo Finance chart API (`GC=F`→`xyz:GOLD`, `^GSPC`→`xyz:SP500`),
wrapped in `CachingDataAdapter`. `1h`/`4h` (4h synthesized from 1h) cover the full
180d window; `5m`/`15m` only cover ~60d (gates degrade gracefully on older portion).
**Cost model:** 5bps round-trip.

| Period | Symbols | Trades | Win Rate | PF | avgR | Total R |
|--------|---------|--------|----------|----|------|---------|
| 180d (Yahoo, 5bps cost) | GOLD + SP500 | 37 (18W/19L) | **50.0%** | **0.68** | **−0.20** | **−7.11** |

### IS / OOS split (70% / 30% time)

| Segment | Cutoff | n | WR | PF | avgR |
|---------|--------|---|----|----|------|
| In-sample | — | 24 | 37.5% | 0.40 | −0.47 |
| Out-of-sample | 2026-05-18 | **12** | **75.0%** | **2.15** | **+0.36** |

> **Caveat:** OOS n=12 is too thin to trust. A 75% WR over 12 trades has enormous sampling
> variance — 8 in a row winning would produce the same result. The IS read (n=24, PF 0.40)
> is the more reliable signal, but 24 trades is still marginal. Do not trade live from this.

### Frictionless baseline (superseded — kept for reference only)

| Period | Symbols | Trades | Win Rate | Total R | Profit Factor |
|--------|---------|--------|----------|---------|---------------|
| 180d (Yahoo, no cost) | GOLD + SP500 | 37 (18W/18L) | 50.0% | 0.0 | 1.0 |

At 1:1R target and 50% WR, frictionless PF = 1.0 is the arithmetic floor — the strategy
exactly breaks even before costs. Any friction tips it negative.

### Legacy windows (different data source — Hyperliquid live feed, no cost model)

| Period | Symbols | Trades | Win Rate | PF |
|--------|---------|--------|----------|-----|
| 7d (Hyperliquid) | GOLD + SP500 | 19 (15W/3L) | 83.3% | 5.0 |
| 14d (Hyperliquid) | GOLD + SP500 | 23 (19W/3L) | — | 6.33 |

These windows are from a different feed (Hyperliquid `xyz:` perps, not Yahoo spot) and
contain no cost model. They are kept for historical reference only — do not use as a seed.

## Known Defects

| Defect | Location | Effect |
|--------|----------|--------|
| 28×-ATR stop cap | Gate 5, line `stop_dist > 2 * atr_15m * 14` | The guard intended to reject structurally unreasonable stops effectively never fires — it allows stops up to 28× the average 15m candle range instead of 2× |
| 1:1R target at 50% WR | Gate 6 | Arithmetic breakeven is PF=1.0; any realistic cost drags it below 1.0; the strategy requires WR consistently above 55% after cost to survive |

## Iteration Log

No iterations run against the 180d Yahoo window. Original 7d/14d Hyperliquid
windows required none. The cost-adjusted 180d result (PF 0.68) is the first
honest baseline and is the starting point for any gate iteration.

Suspected first candidates if iterating:
- Gate 2: Competing-draw threshold is 1.2× — may be too loose (lets through setups with near-equal opposing draws)
- Gate 3: SMT detection has no staleness filter — a 1h SMT from 40 candles ago confirms just as readily as a fresh one
- Gate 5 (28×-ATR): Fix the bug before any other gate iteration (a broken guard silently accepts bad stops)
- Target model: 1:1R target with 50% WR cannot survive crypto-level friction; consider 1.5–2:1 minimum

## Data Constraints
- Requires 4h + 1h + 15m + 5m candles per symbol (min 10 each, 5m min 1)
- Requires correlated-pair candles for SMT: `xyz:SILVER` for GOLD, `xyz:NVDA` for SP500
- Live paper trading: Hyperliquid `xyz:` dex proxies (native forex/futures feeds absent)
- Backtest: Yahoo Finance (`GC=F`, `^GSPC`, `SI=F`, `NVDA`) — `4h` synthesized from `1h`; `5m`/`15m` limited to ~60d

## Commands
```bash
cd traders/znasdaq
uv run python backtest.py    # backtest
uv run python main.py        # paper trading (live)
```
