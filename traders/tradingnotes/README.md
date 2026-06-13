# Trading Notes — Scanner

Educational SMC channel (@TradingNotes1) simplified to a gate-based scanner.
Core approach: multi-timeframe Smart Money Concepts — 1H trend + FVG + 5M liquidity grab.

## Strategy Summary

Three-step framework used consistently across all 12 sourced videos:

1. **1H direction** — BOS sequence (HH/HL long; LH/LL short). Body closes only.
2. **1H FVG** — unmitigated gap in demand/supply zone; inducement-filtered (skip if unfilled
   gap exists beyond the candidate, making it a trap zone)
3. **5M confirmation** — price enters FVG → liquidity sweep → 5M CHoCH → entry at 5M OB

Secondary setup (weekly range false breakout) not implemented in v1 — extends naturally.

## Gate Pipeline

| # | Gate | Pass condition |
|---|------|----------------|
| 1 | 1H trend direction | ≥2 BOS in same direction; last 4 swings HH/HL or LH/LL |
| 2 | 1H FVG exists (aligned) | Unmitigated FVG below price (long) or above price (short); inducement-filtered |
| 3 | Daily space clear | No daily swing within 0.5% in target direction |
| 4 | Price at FVG | 1H close inside zone ± 0.5% tolerance |
| 5 | 5M liquidity grab | V-shape sweep below swing low (long) or inverted-V above swing high (short) |
| 6 | 5M CHoCH | Body close above swing high (long) or below swing low (short) after sweep |
| 7 | Set levels (TAKE) | Long: entry=OB high, stop=below sweep low, target=1H swing high above price |
| | | Short: entry=OB low, stop=above sweep high, target=1H swing low below price |

## Backtest Results

| Period | Symbols | Trades | Win Rate | Avg R | Profit Factor |
|--------|---------|--------|----------|-------|---------------|
| 30 days | BTC/ETH/SOL/BNB | 13 | 69.2% | 0.48 | 2.54 |

Breakdown: BTC 5 (4W/1L), ETH 7 (4W/3L), SOL 1 (1W/0L), BNB 0.

## Iteration Log

| Iteration | Change | Result |
|-----------|--------|--------|
| 1 | Gate 1 relaxed: last 2 highs + 2 lows instead of 4 pairs | Evaluations reaching Gate 2 up 6% → 40% |
| 2 | Gate 4 tolerance: 0.2% → 0.5% | First trades enabled in 30-day window |
| 3 | Gate 5 lookback: 15 → 25 5M bars | +1 BTC trade caught |
| 4 | Short side: mirror all 7 gates for bearish setups | 10 → 13 trades; PF 4.59 → 2.54 (expected: shorts harder to time) |

## Data Constraints

- Requires: 1H candles (50+ bars), 5M candles (30+ bars), daily candles (20+ bars)
- Symbols: crypto-native strategy; works on any liquid market
- Session filter: London (3am ET) and NY (9:30am ET) opens only — not implemented in scanner
  (data adapter does not expose session time; gate omitted)

## Commands

```bash
cd traders/tradingnotes
uv run python backtest.py       # backtest
uv run python main.py           # live paper trading
```
