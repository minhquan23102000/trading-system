# Z Nasdaq — Trader Profile

## Overview
Prop firm trader. Primary: gold (XAUUSD) Asia session. Secondary: NASDAQ (NQ)
premarket/NY. Strategy: Draw on Liquidity continuation model, 1:1R target,
high win rate over high R:R. Trades SMT divergence + FVG entry + failure swing
draws.

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

Data source: Yahoo Finance chart API (`GC=F`→`xyz:GOLD`, `^GSPC`→`xyz:SP500`),
wrapped in `CachingDataAdapter`. `1h`/`4h` (4h synthesized from 1h) cover the
full 180d window; `5m`/`15m` only cover the most recent ~60d (gates degrade
gracefully on the older portion — see `docs/backtest.md`).

| Period | Symbols | Trades | Win Rate | Total R | Profit Factor |
|--------|---------|--------|----------|---------|---------------|
| 180d (Yahoo) | GOLD + SP500 | 37 (18W/18L) | 50.0% | 0.0 | 1.0 |
| 7d (Hyperliquid, legacy) | GOLD + SP500 | 19 (15W/3L) | 83.3% | — | 5.0 |
| 14d (Hyperliquid, legacy) | GOLD + SP500 | 23 (19W/3L) | — | — | 6.33 |

The 180d Yahoo-backed run is the current reference window — far larger
sample than the original 7d/14d Hyperliquid windows (which used the `xyz:`
synthetic perp feed directly and are kept above for history). At 1:1R target,
a 50% WR nets PF≈1.0 — the strategy is breakeven before costs over this
window vs. the strong-but-tiny-sample 7d/14d results. Needs gate tuning
(Gate 2 competing-draw threshold, Gate 3 SMT staleness — see Iteration Log)
before the larger sample is trusted as a seed.

## Iteration Log

No iterations required yet on the 180d Yahoo window. Original 7d/14d
Hyperliquid windows passed with no iteration; the larger sample surfaces a
50% WR / PF≈1.0 baseline. If live trading or further backtests confirm this,
Gate 3 (SMT staleness) and Gate 2 (competing draw threshold 1.2×) are the
most likely candidates to tune first.

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
