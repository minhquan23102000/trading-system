# Z Nasdaq — Strategy Breakdown

## Core Identity
Z Nasdaq is a prop firm trader who made multi-six-figure payouts across Apex,
Topstep, Tradeify, E8, FTMO, and Lucid. He trades gold (XAUUSD) primarily
during Asia session and NASDAQ (NQ) during pre-market/NY. His edge is reading
where price *wants* to go before it gets there — draw on liquidity is the
centerpiece. He runs a 1:1R (or lower) model optimized for high win rate, not
high R:R, because consistency-rule prop accounts punish drawdowns and reward
base hits.

> "Once you have that draw, price is trending towards it. You just get in on a
> continuation. You can easily catch one R, two R."

## Ranked Priorities
1. **Draw on Liquidity** — the single most important concept. Without a
   qualified draw, no trade.
2. **High win rate over high R:R** — 1:1R standard, negative RR acceptable.
   "The lower RR you have, you potentially have a higher win rate."
3. **Protected stop loss** — stop at structural invalidation, not fixed distance.
4. **Continuation over reversal** — "the most high probability trades are always
   continuations."
5. **SMT confirmation** — divergence between correlated pairs at swing
   highs/lows.
6. **Dumb obvious only** — disqualify all competing draws. If hesitant, skip.

## The Setup(s)

### Setup: DOL Continuation (Primary — ~90% of trades)
- **Trigger:** HTF draw identified (failure swings, weak high/low, or unfilled
  HTF gap) + SMT at recent swing extreme + price pulls back into 15m/5m FVG and
  forms an inversion/breaker.
- **Timeframes:** 4h / 1h for bias and draw identification; 15m / 5m for entry.
- **Entry:** At the 15m or 5m breaker/inversion after price taps into a gap
  (FVG). Specifically: after the gap tap, wait for a CISD/breaker candle that
  confirms continuation toward the draw.
- **Stop:** Above/below the swing extreme that would invalidate the continuation
  (the protected swing high/low from which the displacement originated, or the
  gap boundary if tighter).
- **Target:** 1R (standard for S2F/consistency accounts). Alternative: nearest
  failure swing cluster if it's close to 1R. On no-consistency accounts, may
  hold for 2R+ if draw is strong.
- **Does NOT apply when:** Multiple competing draws of equal quality exist; no
  SMT at the recent swing; the draw has already been tapped; price is in
  extended range without clear swing structure.

### Setup: Last Call / Reversal Pullback (rare — ~10% of trades)
- **Trigger:** A HTF reversal has already formed (CISD confirmed) AND price
  pulls back into a gap *before* the draw is taken.
- **Timeframes:** 4h / 1h for reversal confirmation; 1m / 5m for entry.
- **Entry:** At the breaker after the gap rejection. "This will only work if we
  leave the draw untapped before we tap into a gap."
- **Stop:** Above the gap boundary / swing high that the reversal invalidated.
- **Target:** 1R or the full draw if risk allows.
- **Does NOT apply when:** The reversal hasn't been confirmed by CISD; the draw
  was already taken before the pullback; no protected stop exists.

## Key Concepts

### Draw on Liquidity (DOL)
Z's definition: "Areas that the market is most likely to target." Three types,
ranked by preference:
1. **Failure swings** — pivot clusters that failed to break through, building
   up resting liquidity above/below. "My favorite draw liquidity."
2. **Weak highs/lows** — swing points formed *without* tapping into a HTF gap
   or significant liquidity level. Expected to get run because "most people are
   trying to trade that reversal and the market is going to hunt them."
3. **Unfilled higher time frame gaps** — 1h, 4h, daily fair value gaps that
   remain unfilled. Price draws to fill them.

Qualifying a DOL:
- There must be displacement/continuation *toward* the draw (a 4h swing formed
  pointing at it, strong candles in that direction).
- Competing draws must be disqualified (farther away, weaker structure, no
  displacement toward them).
- "Why are we going to target this draw instead of the other? Because we're
  forming continuation towards our draw."

### SMT (Smart Money Technique)
Divergence between two correlated instruments at a swing high/low.
- NQ makes a higher high, ES makes a lower high → bearish SMT → expect reversal
  down.
- XAUUSD makes a higher high, correlated grey pair makes a lower high → bearish
  SMT.
- SMT is used as confirmation that the recent swing will not hold.

### CISD (Change in State of Delivery)
A structure shift — when price breaks a prior swing and the market character
changes direction. Used as a confirmation that the trend has flipped.
- CISD breaker: the level/candle immediately after CISD — used as entry point.

### FVG (Fair Value Gap)
A price imbalance / gap between candles. Used as entry zones when price pulls
back into them. Specifically: 15m and 5m FVGs are entry zones; 1h, 4h, daily
FVGs are draw targets.

### Displacement
A strong, impulsive move that creates a swing and establishes direction toward
a draw. "Strong displacement pullback target these draws."

### Protected Stop Loss
A stop placed at a structural level that would *invalidate* the trade idea —
typically the swing high/low from which displacement originated, or the boundary
of the FVG that was used as entry if it's closer. Not a fixed pip/point
distance.

## Gates (Draft Pipeline)

Gate 1: HTF Structure & Bias — Is there a clear higher timeframe direction?
  Pass: 4h chart shows a recent swing (displacement + pullback) pointing
    toward an un-tapped draw. The swing was NOT formed at a random level.
  Fail: 4h is choppy/range-bound with no clear swing structure, no
    displacement, or the most recent swing has already hit its draw.

Gate 2: Qualified Draw on Liquidity — Is there a qualified, unambiguous DOL?
  Pass: At least ONE of: (a) untapped failure swings on 15m/1h in direction of
    bias, (b) a weak high/low that has not been swept, (c) an unfilled 1h/4h
    FVG with displacement pointing toward it. AND no competing draw of equal
    strength in the opposite direction.
  Fail: No qualified draw found, or two equally strong draws in opposite
    directions within similar distance.

Gate 3: SMT Confirmation — Is SMT present to confirm the reversal/swing?
  Pass: SMT detected between the primary symbol and its correlated pair at the
    most recent HTF swing high (for shorts) or swing low (for longs).
  Fail: No SMT at the relevant swing extreme, or SMT points opposite direction.

Gate 4: Entry Zone Reached — Has price pulled back to a tradable gap?
  Pass: On 15m or 5m, price has tapped into an FVG AND formed either:
    (a) an inversion (FVG gets respected, price reverses from it), or
    (b) a CISD/breaker candle confirming continuation toward the draw.
  Fail: No gap tap yet, or gap was tapped but price blew through it without
    any reaction/inversion.

Gate 5: Protected Stop Exists — Is there a valid structural invalidation point?
  Pass: A clear swing high/low or gap boundary exists that, if breached,
    would invalidate the trade thesis. Stop distance is reasonable (not more
    than ~2x typical ATR on the entry timeframe).
  Fail: No clear structural invalidation point, stop would be purely
    arbitrary.

Gate 6 (Final): Set Entry, Stop, Target — Compute levels and flip to TAKE.
  Pass: All above gates passed. Set:
    - entry = price at the breaker/inversion (or current price if in zone)
    - stop = the structural invalidation level (swing extreme or gap boundary)
    - target = entry + 1×(entry - stop) for longs, entry - 1×(entry - stop)
      for shorts (1:1R), OR the nearest untapped failure swing cluster if it's
      within 1.3R
    - direction = "long" if drawing to upside liquidity, "short" if drawing
      to downside liquidity
  Fail: (This gate always passes if reached — it's the commit point.)

## Anti-Patterns
- Trading without a "dumb obvious" draw: "If you're hesitant about the setup at
  all, if it's iffy, if we have two potential draws on liquidity, you do not
  take the setup."
- Trading reversals at the top: "We want to trade continuation. When we have
  our draw as clear as day, we make another failure swing to our draw."
- Forcing trades when mental fatigue sets in: "Towards the finish line you kind
  of get that mental fatigue and it was rushing me."
- Getting greedy on targets: "Never be greedy with your take profits, especially
  when you're trading prop firms. You want to maximize your win rate."

## Risk Management
- **S2F/consistency accounts:** One high-quality trade per day. If it loses,
  lock out. Risk ~1-2% of account per trade on S2F to build buffer fast, then
  scale down to flip days.
- **No-consistency accounts (Topstep, Apex):** Risk heavier on A++ setups to
  build buffer, then take small flip days ($150-200) to secure payout.
- **Portfolio view:** Think in monthly P&L across all firms, not per-account.
  "A loss is just part of the operating cost as a business."
- Target: 1R standard. Sometimes less than 1R. "I'm not even always targeting
  the exact draw. I'll usually just take like a one R or something."

## Voice & Vocabulary
- "Dumb obvious" — setup quality bar
- "Protected stop" — structural invalidation, not arbitrary
- "Draw" / "draw on liquidity" — where price wants to go
- "Cooked" — what happens when you break your rules
- "Base hit" — small consistent win
- "Flip days" — $150-200 days to hit consistency targets
- "Stack capital" — diversify across multiple firms
- "Continuation" — trade with the trend, not against it
