# Honest-Baseline Investigation Handoff

> **Purpose:** Now that frictionless bias is removed, this document maps the root causes
> behind each trader's real performance and defines the concrete investigation work needed
> before any gate re-tuning is attempted. Do not tune gates until you have read through
> each section — the causes differ per trader and some require bug fixes before measurement
> is even meaningful.
>
> **What changed:** `src/model_trader/backtest/runner.py` now deducts a per-trade cost via
> `_cost_in_r(entry, stop, cost_bps)`. Config key `backtest_cost_bps` (10bps crypto, 5bps
> Yahoo proxies). `traders/portfolio_backtest.py` now prints an IS/OOS split for each trader
> (cutoff = last 30% of each trader's own trade timeline).

---

## Honest Baseline (all numbers cost-adjusted)

| Trader | Trades | WR | PF | avgR | Cost model |
|--------|--------|----|----|------|------------|
| mulham | 686 | 33.6% | **0.79** | −0.17 | 10bps |
| znasdaq | 37 | 50.0% | **0.68** | −0.20 | 5bps |
| tradingnotes | 196 | 57.1% | **0.82** | −0.11 | 10bps |

### IS / OOS detail

| Trader | IS PF | IS n | OOS PF | OOS n | OOS cutoff |
|--------|-------|------|--------|-------|------------|
| mulham | 0.74 | 478 | 0.92 | 206 | 2026-04-21 |
| znasdaq | 0.40 | 24 | 2.15 | 12 | 2026-05-18 |
| tradingnotes | 0.68 | 120 | 1.06 | 76 | 2026-04-21 |

**Portfolio:** $10k → $2,532 over 180d, MaxDD 81.9%, Sharpe −2.02. All strategies lose
money independently; they are genuinely uncorrelated (pairwise r near zero), but
diversifying three losing strategies produces a diversified loss.

---

## Trader 1 — Mulham

### Root cause A: WR is at-breakeven even frictionlessly

The 2:1 minimum target (Gate 9 `actual_rr >= 2.0`) requires WR > 33.3% to generate
positive expectancy. The 180d WR is 33.6% — 0.3% above the frictionless break-even
floor. Any friction, spread, or slippage flips it negative.

The frictionless +0.03 avgR is noise, not edge. The 52d/15m Hyperliquid window's 46.5%
WR was a regime artefact or feed interaction — it does not hold in the wider sample.

### Root cause B: 0.20% stop floor × 10bps cost = 0.5R minimum per trade

`_cost_in_r(entry, stop, 10bps)` at the 0.20% floor: `(entry × 0.0010) / (entry × 0.0020) = 0.5`.
At 686 trades with stops clustered near the floor, total friction is several hundred R.
Observed cost: `22.78 (frictionless total_r) − (−114.59) = 137.37R` across 686 trades = 0.20R/trade avg.
Average implied stop pct ≈ `10bps / 0.20R = 0.50%` — many stops are wider than the floor
but still tight relative to move size.

### Root cause C: Degenerate range in Gate 4

`range_high = highs_15m_rng[-1]["price"]` and `range_low = lows_15m_rng[-1]["price"]` are taken
from the most recent swing high and swing low **independently** — they need not form a
sequentially coherent HP range. If the last swing high preceded the last swing low but both
are drawn from different structural legs, the "range" is a synthetic construct that does not
correspond to Mulham's anchored-displacement HP range definition. This allows setups through
Gate 4 that are not actually high-probability ranges.

### Root cause D: High frequency amplifies cost

686 trades over 180d = 3.8 trades/day. Every additional trade at −0.17R avgR deepens the
loss. A strategy that merely reduced frequency to true high-probability setups would reduce
total loss even before fixing edge.

### IS/OOS interpretation

IS PF 0.74, OOS PF 0.92 — the OOS period (post-2026-04-21) is slightly better, not
sharply worse. This suggests the strategy is consistently marginal rather than severely
overfit. The regime in OOS (n=206) appears slightly more favorable for the gates, but
both halves are sub-1.0 after cost.

### Investigation questions

1. **Gate 4 range validity:** How many of the 686 TAKE trades had `range_high < range_low`
   before the `range_size <= 0` guard caught it? And how many had `range_high > range_low`
   but the swings were from non-contiguous legs (degenerate HP range)? Add a debug log of
   `(range_high, range_low, direction, ts)` for every TAKE signal and audit a sample.

2. **Stop distribution:** Histogram the implied stop pct for all 686 trades. What fraction
   are at the 0.20% floor? What is the p50/p90 stop pct? If the median is near 0.20%,
   the cost problem is structural and requires either raising the floor (which reduces
   frequency) or accepting wider stops (which requires higher WR to compensate).

3. **WR by direction:** Is the 33.6% WR symmetric between longs and shorts, or is one
   side dragging? The scanner allows both; SOL's 32.1% WR suggests BTC/SOL are
   directionally skewed.

4. **Kill zone concentration:** What fraction of signals fire in each kill zone
   (Asia/London/NY)? Asia kill zone signals on crypto 5m data may fire more often
   (thin market, more FVG creation) but with worse follow-through.

5. **Gate 4 fix experiment:** Redefine the HP range as the swing immediately preceding
   the most recent displacement (the range that displacement broke out of), rather than
   the most recent high/low pair. Backtest before/after on the same 180d window. If WR
   improves significantly, the degenerate range was a major contributor.

6. **Target model:** The 2:1 floor captures the structural swing if it is ≥2R (Gate 9),
   else defaults to `entry + 2R`. Is the 2R default target (a fixed multiple, not a
   structural level) consistently filled? A fixed-multiple target on a volatile 5m setup
   may be more reliable than a distant structural swing; or it may be worse. Isolate.

---

## Trader 2 — Znasdaq

### Root cause A: 28×-ATR stop cap bug

Gate 5 (`PROTECTED_STOP`), line:
```python
if atr_15m <= 0 or stop_dist <= 0 or stop_dist > 2 * atr_15m * 14:
```
`atr_15m` = mean 15m candle range over last 14 candles. The guard is intended to reject
structurally unreasonable stops, but `2 * atr_15m * 14 = 28 × (mean 15m range)` is
roughly a 7-day range for GOLD — effectively never triggered. The intended cap is likely
`2 * atr_15m` (2 ATR, not 28). Until this is fixed, any stop distance is accepted and
the stop level has no quality control.

**Fix required before any other gate iteration:** `stop_dist > 2 * atr_15m * 14` →
`stop_dist > 2 * atr_15m`. Then re-run the 180d backtest and report new trade count.
If fixing the cap removes most trades, the structural stops were routinely enormous —
which explains why 5bps cost still hurts (wide stop = low cost-in-R, so this isn't
a cost problem, it's a stop-too-far-from-entry accuracy problem: price rarely reaches
the 1:1R target before the wide stop is never hit but the trade wanders off).

Actually clarify: wide structural stops *lower* cost-in-R (cost/risk shrinks as stop
widens). The PF 0.68 is more likely from WR degradation — at 50% WR and 1:1R target
the arithmetic PF after cost is `(0.5 × 1.0 − c) / (0.5 × 1.0 + c)` where c is
mean cost-in-R. At PF 0.68: `0.5(1−c)/0.5(1+c) = 0.68 → c ≈ 0.19R`. Average
implied stop ≈ `5bps / 0.19R = 0.026%` — unexpectedly tight for a structural stop
strategy on GOLD. This suggests either very tight structural stops or the stop
computation is inconsistent in the buggy gate.

### Root cause B: Thin sample limits interpretation

37 total trades over 180d = 0.21 trades/day. At this frequency, a 5-trade run of good
or bad luck dominates the PF reading. IS n=24, OOS n=12 — the OOS PF 2.15 on n=12
cannot be distinguished from sampling noise.

The key question is not "why is OOS better?" but "why so few trades?" With two symbols
(GOLD, SP500), the strategy is firing one trade every ~5 days per symbol. If the real
trader fires 2-3 trades per day, the scanner's gates are far too conservative or the
data source (Yahoo proxies, synthetic Hyperliquid perps) does not replicate the live
feed's structure.

### Root cause C: 1:1R target model has zero margin at 50% WR

At 1:1R and 50% WR, frictionless PF = 1.0. Any cost makes it sub-1.0. The real trader
accepts less than 1R on "base hit" trades and compensates with high consistency. An
automated scanner that fires at exactly 1:1R and 50% WR has no buffer.

The strategy's actual win rate in live trading is reportedly high (7d: 83%, 14d: ~82%).
Either the live win rate is unsustainably elevated (small window), or the gates are
misclassifying entries that the real trader would recognize as high-conviction vs skip.

### IS/OOS interpretation

IS PF 0.40 vs OOS PF 2.15 is a suspicious regime flip, not evidence of OOS edge. The
more likely explanation: the IS period (pre-2026-05-18, ~70% of the timeline) covered
a sideways/choppy gold market while OOS caught a trending period with clean DOL
continuations. This is regime sensitivity, not learnable skill from the scanner.

### Investigation questions

1. **Fix the 28×-ATR bug first.** Change `stop_dist > 2 * atr_15m * 14` to
   `stop_dist > 2 * atr_15m`. Re-run. Report: new trade count, new PF, new stop distribution.

2. **Why so few trades?** Add gate-by-gate rejection logging (the `result.reason` field is
   already set). After a full 180d run, count how many evaluations were rejected at each
   gate and print a funnel. The bottleneck gate determines whether the strategy is too
   conservative or the data source is inadequate.

3. **SMT staleness:** Gate 3 accepts any 1h SMT divergence ever detected, not just recent
   ones. If the most recent 1h SMT was 30 candles ago, is it still valid confirmation?
   Add a `max_age_candles` parameter to `SMTDetector` and test cutoffs (5, 10, 20 candles).

4. **Competing draw threshold:** Gate 2 disqualifies if competing draw is within 1.2× the
   primary draw's distance. Is 1.2× the right threshold? A competing draw at 1.19× still
   blocks a valid setup. Try 1.0× (exact-equal) and 1.5× and compare trade counts.

5. **1:1R vs 1.5:1R target:** The real trader accepts 1R. But OOS PF 2.15 at n=12 on
   1:1R suggests the moves sometimes go further. Test a 1.5:1R floor on the same gate
   pipeline: does it filter out the marginal 50/50 trades (higher WR) or does it just
   reduce frequency with no WR benefit?

6. **Yahoo vs Hyperliquid feed difference:** The 7d/14d Hyperliquid results showed 80%+
   WR. Are the Hyperliquid `xyz:GOLD` and `xyz:SP500` perps in the backtest period
   exhibiting structural properties (gap patterns, swing formation) fundamentally different
   from the Yahoo `GC=F`/`^GSPC` proxies used in the 180d run? Consider running the scanner
   on the live Hyperliquid feed for 30 days in paper-trade mode and comparing real-time
   gate pass rates vs the Yahoo backtest.

---

## Trader 3 — Tradingnotes

### Root cause A: Stop distance is dominated by sweep-wick extremes

Stop = `sweep_extreme × (1 − 0.0005)` — just below the lowest point of the 5M sweep
wick. Entry = top of last bearish 5M OB before CHoCH. On a V-shape sweep, the OB top
is typically close to (or even above) the swing low being swept — meaning the stop is
BELOW the swing low that was swept, while the entry is ABOVE it. The risk = OB top − sweep low.

On tight crypto wicks this can be <0.10% of price. Observed average: implied risk ≈ 0.13%
(from `_cost_in_r ≈ 0.77R` at 10bps: `10bps / 0.13% = 0.77R`).

0.77R/trade in cost is catastrophic: on a 57% WR system with variable RR capped at 3.0×,
the frictionless +0.64R avgR collapses to −0.11R. Frictionless PF 2.5 was an artefact
of the tight-stop model, not real edge.

### Root cause B: OOS shows marginal edge (PF 1.06) — still fragile

The WR is consistent across IS (56.7%) and OOS (57.9%). The IS/OOS flip from PF 0.68 to
1.06 is almost entirely a cost artifact: at 57% WR with tight stops, a small improvement
in average stop width or average win RR pushes across the breakeven line. The OOS period
(post-2026-04-21) may have had slightly wider sweep wicks (higher volatility), which
paradoxically HELPS: wider stop → lower cost-in-R → less friction. If this holds, the
strategy's edge is conditional on market volatility being high enough to make stops
"meaningfully wide."

### Root cause C: Short side likely dragging

SOL: 9W/19L at 32.1% WR is a severe outlier. The other symbols all show 56-64% WR.
Short setups on SOL in a bull trend (SOL rallied through the 180d window) would
systematically lose. The scanner fires shorts symmetrically; the human trader would
filter by macro context.

### Root cause D: No session filter

The strategy explicitly requires London (3am ET) or NY (9:30am ET) sessions. The scanner
fires at any time. Off-session setups likely have lower follow-through and noisier
liquidity sweeps. This is a known omission (noted in Data Constraints) but its quantitative
impact is unmeasured.

### IS/OOS interpretation

IS PF 0.68 (n=120) vs OOS PF 1.06 (n=76). IS covers the Jan–Apr period; OOS covers
Apr–Jun. The OOS period's slight improvement in PF is plausibly explained by wider
stop distances (higher realized volatility in crypto Q2 2026) reducing cost-in-R.
If true, the scanner has no real WR-based edge — the marginal OOS PF is a cost-model
artefact, not a scanner quality signal.

### Investigation questions

1. **Stop width distribution:** Histogram `risk / entry_price` for all 196 trades.
   Are stops clustered below 0.15%? If yes, any crypto cost model with >3bps will
   destroy this strategy. The fix is structural: require a minimum stop distance (as
   mulham does at 0.20%) and accept fewer, better-spaced trades.

2. **Long vs short breakdown:** Split all 196 trades by direction and report WR/PF
   separately. If short WR is <40% across all symbols, disabling shorts and running
   longs-only is the simplest lever. Add `direction_filter: "long"` to config and
   re-run.

3. **Session filter:** Filter backtest evaluations to London (03:00–05:00 ET) and
   NY (09:30–11:30 ET) only. The `evaluate_at(ts)` call already has the timestamp;
   a 2-line UTC→ET conversion and hour check before Gate 1 implements this exactly
   as the original strategy specifies. Measure the trade-count and WR impact.

4. **SOL regime check:** Run 180d backtest on BTC+ETH+BNB only (remove SOL). Does
   PF improve materially? If yes, SOL setups are regime-specific (bull run kills
   short setups). Consider a macro filter for SOL (e.g., only take longs when SOL
   is above its 200-period 4h MA).

5. **Stop floor test:** Add `min_stop_pct: 0.003` (0.30%) to Gate 7. Trades with
   stop distance < 0.30% are skipped. At 0.30% stop: `_cost_in_r = 10bps/0.30% = 0.33R`.
   A 57% WR system with 2:1 capped target can survive 0.33R cost:
   `(0.57×2 − 0.43×1) − 2×0.33 = 1.14−0.43−0.66 = +0.05R avgR` (barely). Measure
   how many trades survive the filter and whether WR shifts.

6. **Inducement filter effectiveness:** Gate 2 skips FVGs that have a lower FVG below
   them. Are the skipped setups actually worse (higher loss rate)? Add a counter for
   inducement-filtered events and, separately, test removing the inducement filter to
   see if trade count doubles but WR drops (which would confirm the filter is working).

---

## Cross-Trader Themes

### 1. Cost sensitivity is stop-width sensitivity

All three strategies use LTF (5m/15m) entry structures with tight structural stops.
The tighter the stop, the higher `_cost_in_r`. Increasing minimum stop distance is the
single lever that uniformly reduces cost impact — at the price of fewer trades and
potentially lower WR (wider stops get hit more often when wrong).

The right framing: **there is a minimum tradable stop width** for each cost model.
For 10bps crypto: `cost_in_r = 0.5R` at 0.20% stop. A 2:1 system needs WR > 33% to
survive 0.5R cost. A 1:1 system (znasdaq) needs WR > 61% to survive 0.33R cost.
Tighter stops require even higher WR — eventually impossible.

| System | Min stop for breakeven at 10bps | Required WR at 2:1 |
|--------|--------------------------------|---------------------|
| Mulham (2:1, 33.6% WR) | 0.30% | 38% at 0.33R cost |
| Tradingnotes (var RR, 57% WR) | 0.30% | Survives at 0.33R |
| Znasdaq (1:1, 50% WR) at 5bps | 0.30% | 58% WR needed |

### 2. Sample sizes are insufficient for IS/OOS decisions

Mulham (n=686) is the only trader with enough trades to draw tentative conclusions.
Znasdaq (n=37) and to a lesser extent tradingnotes (n=196) cannot distinguish edge
from noise. The investigation priority should be: fix bugs → increase trade frequency
(if gates are too conservative) → accumulate a larger honest sample → iterate gates.

### 3. Gate bugs must be fixed before gate tuning

Two confirmed bugs alter measurement:
- **Mulham Gate 4:** Degenerate range (last swing H and L need not be a coherent pair)
- **Znasdaq Gate 5:** 28×-ATR stop cap (`* 14` factor)

Tuning any other gate before fixing these is tuning against a corrupted signal.
Fix order:
1. Fix znasdaq Gate 5 ATR cap: `2 * atr_15m * 14` → `2 * atr_15m`
2. Fix mulham Gate 4 range: enforce sequential swing pair (swing high from BEFORE the
   most recent swing low for longs; swing low from BEFORE most recent swing high for shorts)
3. Re-run full 180d backtest
4. Read the new baseline — that is the actual starting point for gate iteration

### 4. Regime sensitivity is unmeasured

All three traders were backtested over the same 180d window (Jan–Jun 2026 approximately).
Crypto was in a mixed/bullish regime. Gold (via Yahoo proxies) had specific trending periods.
The IS/OOS split by time (30% = last ~54d) is a single regime slice. A cross-validation
across multiple 90d windows would give a more reliable picture but requires >1 year of data
per trader — achievable for mulham (Binance) and tradingnotes (Binance), harder for znasdaq
(Yahoo 5m limited to ~60d of history).

---

## Work Priority

| Priority | Trader | Action | Expected signal |
|----------|--------|--------|-----------------|
| P0 | znasdaq | Fix Gate 5 ATR cap (`* 14` → remove) | New trade count and PF after fix |
| P0 | mulham | Fix Gate 4 degenerate range (enforce sequential swing pair) | WR shift and frequency change |
| P1 | tradingnotes | Add minimum stop distance gate (0.30%) | Trade count + PF delta |
| P1 | tradingnotes | Add session filter (London/NY only) | WR shift |
| P1 | tradingnotes | Split long/short results; test longs-only | PF delta |
| P2 | mulham | Gate rejection funnel (log reason counts) | Identify dominant kill gate |
| P2 | znasdaq | Gate rejection funnel | Why 0.21 trades/day |
| P2 | znasdaq | SMT staleness parameter sweep | PF/trade-count tradeoff |
| P3 | all | Cross-validate over 3 × 90d windows (mulham/tradingnotes) | Regime sensitivity |
| P3 | znasdaq | Paper-trade on live Hyperliquid feed for 30d | Validate Yahoo vs live feed |

Do not update `portfolio.yaml` seeds until P0 items are resolved and re-run.
