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

### Cost-adjusted baseline (current)

**Data source:** Binance spot klines (BTC/ETH/SOL/BNB), wrapped in `CachingDataAdapter`.
**Period:** 180d | **Cost model:** 10bps round-trip

| Period | Symbols | Trades | Win Rate | Avg R | Total R | Profit Factor |
|--------|---------|--------|----------|-------|---------|---------------|
| 180d (Binance, 10bps cost) | BTC/ETH/SOL/BNB | 196 (112W/84L) | **57.1%** | **−0.11** | **−22.33** | **0.82** |

Per-symbol trade counts (W/L): BTC 57 (34/23), ETH 54 (32/22), SOL 28 (9/19), BNB 57 (37/20).

> **Why costs hit hard:** stop = 0.05% below the 5M sweep wick extreme; entry = 5M OB high
> (close to wick). Average implied stop distance ≈ 0.13% of price. At 10bps cost,
> `_cost_in_r ≈ 10bps / 0.13% ≈ 0.77R per trade` — cost exceeds an average win's margin.

### IS / OOS split (70% / 30% time)

| Segment | Cutoff | n | WR | PF | avgR |
|---------|--------|---|----|----|------|
| In-sample | — | 120 | 56.7% | 0.68 | −0.21 |
| Out-of-sample | 2026-04-21 | 76 | 57.9% | **1.06** | **+0.04** |

OOS shows marginally positive PF (1.06) — the WR is consistent (57% both halves), but cost
absorption is near the break-even line. This is the most honest read of any remaining edge:
marginal, fragile, and entirely dependent on whether stop distances can be widened.

### Frictionless baseline (superseded — kept for reference only)

| Period | Symbols | Trades | Win Rate | Avg R | Total R | Profit Factor |
|--------|---------|--------|----------|-------|---------|---------------|
| 180d (Binance, no cost) | BTC/ETH/SOL/BNB | 196 (112W/84L) | 57.1% | +0.64 | +126.13 | 2.5 |

The PF 2.5 figure and +0.64 avgR are artefacts of near-zero implied stop distances — the
sweeping wick drives entry and stop very close together. With any real cost model they collapse.

### Legacy window (Hyperliquid, no cost model)

| Period | Symbols | Trades | Win Rate | Avg R | PF |
|--------|---------|--------|----------|-------|----|
| 30d (Hyperliquid) | BTC/ETH/SOL/BNB | 13 | 76.9% | +0.78 | 4.44 |

Too small a sample; different feed. Kept for history only.

## Iteration Log

| Iteration | Change | Result |
|-----------|--------|--------|
| 1 | Gate 1 relaxed: last 2 highs + 2 lows instead of 4 pairs | Evaluations reaching Gate 2 up 6% → 40% |
| 2 | Gate 4 tolerance: 0.2% → 0.5% | First trades enabled in 30-day window |
| 3 | Gate 5 lookback: 15 → 25 5M bars | +1 BTC trade caught |
| 4 | Short side: mirror all 7 gates for bearish setups | 10 → 13 trades; short PF 0.50 (3 trades, 1W/2L) |
| 5 | `MAX_RR=3.0` cap on target distance | Frictionless PF 2.54 → 4.44 on 30d window |

All iterations above were calibrated on the **30d / Hyperliquid / frictionless** window and
do not transfer directly to the 180d / Binance / cost-adjusted baseline.

## Known Issues

| Issue | Location | Effect |
|-------|----------|--------|
| Tight stop vs cost | Gate 7 stop formula | Stop = 0.05% below sweep wick; implied avg risk ≈ 0.13% of price; 10bps cost = 0.77R/trade — dominant cost |
| Short bias: 9W/19L SOL | Full pipeline | SOL short setups heavily loss-making in 180d window; long/short breakdown not isolated |

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
