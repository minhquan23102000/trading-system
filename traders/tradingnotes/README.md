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

Data source: Binance spot klines (BTC/ETH/SOL/BNB), wrapped in
`CachingDataAdapter` — years of native history at every configured
timeframe.

| Period | Symbols | Trades | Win Rate | Avg R | Total R | Profit Factor |
|--------|---------|--------|----------|-------|---------|---------------|
| 180 days (Binance) | BTC/ETH/SOL/BNB | 196 (112W/84L) | **57.1%** | **+0.64** | **+126.13** | **2.5** |
| 30 days (Hyperliquid, legacy) | BTC/ETH/SOL/BNB | 13 | 76.9% | +0.78 | — | 4.44 |

Per-symbol (180d): BTC 57 (34W/23L), ETH 54 (32W/22L), SOL 28 (9W/19L), BNB 57 (37W/20L).
By direction is not broken out for the 180d run; the original 30-day window
(long 10/13, PF 4.56; short 3/13, PF 4.00) is kept above as a reference but
is too small a sample to compare directly against the 180d figures. The
wider sample's PF (2.5) is lower than the 30d window's (4.44) — expected,
since 30d was a small, possibly favorable sample; 196 trades over 180d is
the more reliable baseline going forward (use this for `portfolio.yaml`'s
`seed_pf`/`seed_n`).

## Iteration Log

| Iteration | Change | Result |
|-----------|--------|--------|
| 1 | Gate 1 relaxed: last 2 highs + 2 lows instead of 4 pairs | Evaluations reaching Gate 2 up 6% → 40% |
| 2 | Gate 4 tolerance: 0.2% → 0.5% | First trades enabled in 30-day window |
| 3 | Gate 5 lookback: 15 → 25 5M bars | +1 BTC trade caught |
| 4 | Short side: mirror all 7 gates for bearish setups | 10 → 13 trades; short PF 0.50 (3 trades, 1W/2L) |
| 5 | `MAX_RR=3.0` cap on target distance (entry ± 3×risk) | PF 2.54 → **4.44**, WR 69.2% → **76.9%**; short PF 0.50 → 4.00 (3 of 4 losers had planned RR > 3.0) |

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
