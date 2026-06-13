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

Data source: Hyperliquid (`xyz:GOLD`, `xyz:SP500`). Live fetch, no
synthetic data. Two independent windows run on first implementation.

| Period | Symbols | Trades | Win Rate | Avg R | Profit Factor |
|--------|---------|--------|----------|-------|---------------|
| 7d     | GOLD + SP500 | 19 (15W/3L) | 83.3% | 0.67 | 5.0 |
| 14d    | GOLD + SP500 | 23 (19W/3L) | 86.4% | 0.73 | 6.33 |

No iteration required — both windows cleared PF > 1.3 on first
implementation. Main caveat: 18-23 closed trades per window is below
the 50-trade confidence bar; treat results as directionally strong,
not statistically final.

## Iteration Log

No iterations required. Initial gate logic passed both backtest windows
comfortably. If live trading surfaces consistent leakage, Gate 3 (SMT
staleness) and Gate 2 (competing draw threshold 1.2×) are the most
likely candidates to tune first.

## Data Constraints
- Requires 4h + 1h + 15m + 5m candles per symbol (min 10 each, 5m min 1)
- Requires correlated-pair candles for SMT: `xyz:SILVER` for GOLD, `xyz:NVDA` for SP500
- Symbols must exist on Hyperliquid (native forex/futures feeds absent; xyz dex proxies used)

## Commands
```bash
cd traders/znasdaq
uv run python backtest.py    # backtest
uv run python main.py        # paper trading (live)
```
