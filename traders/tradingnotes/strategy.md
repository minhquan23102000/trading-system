# Trading Notes — Strategy Breakdown

## Core Identity
Trading Notes is a simplification-first SMC education channel. The host distills Smart Money
Concepts into repeatable, rule-based frameworks for retail traders. Their edge is clarity: they
strip ICT complexity to 3-4 actionable steps and consistently demonstrate the same core setup
across all markets (forex, crypto, gold, stocks). Every video converges on one central thesis:
institutions need your stop losses to fill their positions — learn to position on the right side
of that mechanic.

## Ranked Priorities
1. **Multi-timeframe confluence** — "stack probabilities" using daily/1H/5M hierarchy; if you can't
   read direction clearly on a TF, move to the next pair
2. **Liquidity sweep before entry** — "before a valid change of character, we want to see price sweep
   a pool of liquidity"; entering before the sweep = providing liquidity, not taking it
3. **FVG as the entry zone** — "the fair value gap is where institutional decisions were made"; the
   optimal entry is inside the HTF FVG, not at current price
4. **BOS/CHoCH structure** — only trade in direction of confirmed BOS; CHoCH is the reversal signal;
   "wicks alone don't count — we need that confirmation close"
5. **Inducement/fishing trap avoidance** — "the lowest isn't always the strongest"; ignore obvious
   zones that have an imbalance sitting below them (those are traps)
6. **Session timing** — London open (3am ET) and NY open (9:30am ET) are the only windows where
   "institutional participation activates" liquidity

## The Setups

### Setup 1: SMC Multi-Timeframe (Primary — taught in every video)

- **Trigger:** HTF (1H) trend confirmed via BOS sequence (HH/HL for bullish, LH/LL for bearish).
  An unmitigated FVG exists on 1H aligned with the trend direction. Price pulls back into that
  FVG zone. LTF (5M) shows a liquidity grab (wick below recent swing low for longs, above for
  shorts) followed by a structural shift (CHoCH: candle body closes above recent 5M swing high).
- **Timeframes:** 1H for direction + FVG; 5M for entry trigger; Daily for context space check
- **Entry:** Limit order at the top of the 5M order block (last bearish candle before the 5M
  impulsive bullish move that caused the CHoCH). Do NOT enter on the CHoCH itself — wait for
  the pullback to the OB.
- **Stop:** Below the low of the 5M liquidity grab (the sweep wick). If price revisits that low,
  the setup is invalidated.
- **Target:** Previous swing high on 1H (first visible liquidity pool above). Partial exit at 1:2;
  trail stop on remainder. "You exit when price approaches the next pool of liquidity."
- **Valid FVG conditions (all required):**
  - Unmitigated (price has not returned since creation)
  - Formed AFTER a 1H BOS (not before)
  - Located in lower 50-61.8% of the overall HTF move (higher priority)
  - Size matters: prefer larger FVGs; skip tiny gaps
  - Not sitting directly under major resistance that would block the move
- **Valid CHoCH conditions (for high-prob setup, from CHoCH video — 4 criteria):**
  - Price reversed from a higher-timeframe supply/demand zone
  - Liquidity sweep occurred before the CHoCH (equal highs/lows taken)
  - Double zone breakout (impulse broke through two consecutive supply/demand zones)
  - Volume confirmation: CHoCH candle volume higher than preceding candles
- **Does NOT apply when:**
  - Trend is unclear / price in consolidation on 1H
  - FVG already mitigated or in upper 50%+ of move (weak zone)
  - Daily TF has a major level directly in front of price (manipulation risk)
  - CHoCH is a minor internal one — must originate from the last major swing that caused the BOS
  - Outside London/NY session windows

### Setup 2: Weekly Range False Breakout (Secondary)

- **Trigger:** Previous week's high/low marked. On 1H chart, a candle BODY closes outside the
  weekly range (above high or below low). Then next 1H candle closes BACK INSIDE the range.
- **Timeframes:** Weekly for range; 1H for entry signals
- **Entry:** Market order (or tight limit) on the close of the re-entry candle back inside range
- **Stop:** Exact extreme of the breakout move (highest high above range, or lowest low below range)
- **Target:** 2x the stop loss size (fixed 2R). Alternative: opposite side of the weekly range.
- **Does NOT apply when:**
  - Breakout is excessively large (stop would be >2% of price) — use nearest key level instead
  - Price re-enters but immediately exits again (no follow-through)
  - Middle of weekly range (no edge zone)

### Setup 3: First 15-Minute Opening Range (Session-Based)

- **Trigger:** At 9:30am NY time. First 15M candle marks the range. Range must be ≥20-25% of the
  14-day ATR. Volume of the 15M candle should be above the 20-bar volume MA (strong confirmation).
- **Timeframes:** 15M to box the range; 5M for reversal candle
- **Entry:** On 5M, wait for reversal candle (hammer/inverted hammer or bullish/bearish engulfing)
  to form OUTSIDE the 15M range, within a 60-90 minute window after open. Enter on break of
  reversal candle in the direction OPPOSITE to the manipulation candle.
  - Hammer below range: enter at break of next 5M candle above hammer high
  - Bearish engulfing above range: enter at low of previous green candle
- **Stop:** Below the low of the reversal candle (hammer) or above the high (inverted/bearish)
- **Target:** Opposite side of the 15M range box (TP1 = near side of box, TP2 = far side)
- **Does NOT apply when:**
  - 15M candle is still forming (must be fully closed)
  - Range is <20% of ATR (not a manipulation candle)
  - Volume is below 20-bar MA (no institutional footprint)
  - No reversal candle appears within 90 minutes — skip, come back tomorrow
  - Reversal candle forms INSIDE the box (doesn't count, must be outside)

## Key Concepts

- **BOS (Break of Structure):** Candle BODY closes above previous swing high (bullish) or below
  previous swing low (bearish). Wicks alone never qualify. "If you're on the hourly chart, you
  need an hourly candle to close above that high."
- **CHoCH (Change of Character):** Originates from the last swing high/low that produced the most
  recent BOS. In a bullish market, bearish CHoCH = price closes below the last major low that
  initiated the upward BOS. "A change of character is literally the market switching from one
  character to the other."
- **CHoCH+ (stronger signal):** Price formed a lower high BEFORE breaking the bullish structure.
  This indicates weakness before the reversal — higher conviction.
- **Fair Value Gap (FVG):** Three-candle imbalance. Bullish FVG: first candle HIGH does not
  overlap third candle LOW. Bearish FVG: first candle LOW does not overlap third candle HIGH.
  The zone = rectangle from first candle wick to third candle wick.
- **Order Block (OB):** Last opposing candle before a strong impulsive move that causes BOS.
  Validity requires: (1) liquidity sweep of prior high/low, (2) FVG/imbalance created after,
  (3) unmitigated, (4) led to BOS or CHoCH.
- **Liquidity Grab:** Price wicks below recent swing low (bullish) or above swing high (bearish)
  — taking stop losses — then reverses. The V-shaped reaction is the signal. "If you can't spot
  the liquidity, you ARE the liquidity."
- **Inducement Zone / Fishing Zone:** Appears to be a valid OB/FVG but has an imbalance below
  it (bullish) — price must fill that imbalance first, so this zone is a trap. True zone is
  identified by which zone generated the most powerful BOS impulse. The lowest zone is NOT
  always the strongest.
- **External vs Internal Structure:** External = the major swing high/low that created the last BOS.
  Internal = all swings between external levels. CHoCH is only valid when price breaks the
  EXTERNAL major low (not an internal one). Internal breaks = minor CHoCH = do NOT trade.
- **Liquidity Types (priority order):** Session highs/lows (highest) → equal highs/lows (double
  tops/bottoms) → trend line liquidity (stacked pivot lows in trend) → internal FVGs (lowest)
- **Inducement (liquidity trap):** "Before price makes a significant move down from a supply zone,
  it will typically first take out all liquidity sitting above it — almost always." Wait for the
  sweep before entering.
- **External Liquidity:** Sits outside the range (above main swing high or below main swing low).
  This is the real target for smart money. Internal liquidity is fuel to reach external.
- **Manipulation Candle (Opening Range):** Fast, aggressive opening candle ≥20-25% of 14-day ATR
  that sweeps liquidity to let institutions fill positions before the real directional move.
- **Volume Confirmation:** CVD (Cumulative Volume Delta) above zero = buyers dominant. POC of
  weekly volume profile = dynamic support/resistance. Enter longs only above POC.

## Gates (Draft Pipeline)

The primary tradable setup for automation is Setup 1 (SMC Multi-Timeframe). It uses available
detectors and maps cleanly to the gate framework.

```
Gate 1: 1H trend direction
  Pass: Clear BOS sequence — last 4+ swings on 1H show HH/HL (bullish) or LH/LL (bearish)
  Fail: Mixed structure / consolidation / fewer than 2 valid BOS in recent history

Gate 2: 1H unmitigated FVG exists (aligned with trend)
  Pass: At least one unmitigated bullish FVG exists below current price (for bullish bias);
        FVG is in the lower 61.8% of the move from last major low to last major high
  Fail: No unmitigated FVG; or all FVGs already mitigated; or FVGs only in upper 50%

Gate 3: Daily context space clear
  Pass: Current price is in open space on daily TF — no major daily swing level within 0.5%
        of current price above (for bullish). Price has room to move.
  Fail: Price is directly under a major daily resistance level

Gate 4: Price at/near the HTF FVG zone
  Pass: Current 1H close is within the identified FVG zone (or within 0.1% above it)
  Fail: Price is far above the FVG zone (missed the pullback) or hasn't returned yet

Gate 5: 5M liquidity grab detected
  Pass: Within last 15 bars on 5M, price wicked below a recent 5M swing low (bullish bias)
        and the candle BODY closed back above that swing low — clean V-shape sweep
  Fail: No sweep detected; or price closed below the swing low (potential trend continuation)

Gate 6: 5M structural shift (CHoCH bullish)
  Pass: After the liquidity grab, a 5M candle BODY closes above the most recent 5M swing high
        (confirming the short-term downtrend has ended and buyers stepped in)
  Fail: No bullish structure shift; price continuing lower after the sweep

Gate 7 (FINAL — set levels and take):
  Entry:  Top of the 5M order block (last bearish candle before the impulsive 5M bullish move)
  Stop:   Below the 5M liquidity grab low (the sweep wick low)
  Target: Previous 1H swing high (first visible buy-side liquidity pool on 1H)
  Direction: "long" (mirror all gates for short setups)
```

**Note on inducement filter (Gate 2 refinement):** If there is an imbalance/FVG sitting below
the identified 1H FVG zone, the 1H FVG is an inducement zone — skip it and use the lower zone
(or wait for the lower imbalance to be mitigated first). Implementation: after detecting the
primary FVG, check whether an unmitigated FVG exists below it; if yes, skip upper one.

## Anti-Patterns
- "Do NOT buy at the top [of the weekly range]. Do NOT sell at the bottom. In the middle — do
  nothing."
- "If you can't clearly determine the market direction in a specific timeframe, move on to the
  next trading pair immediately."
- "Don't trade the chalk [CHoCH] as a breakout. The chalk level is not a key entry level — it's
  a signal." Wait for the pullback to the OB.
- Don't trade minor CHoCH (internal structure break). "A minor change of character alone cannot
  be considered a sign of market structure shift."
- Never use wicks to confirm BOS or CHoCH — always the candle body.
- "Order blocks are one-time use opportunities — once mitigated, they're done."
- Don't trade outside London/NY session windows (Asian session = consolidation, low volume).
- "Never have more than three active trades running simultaneously."

## Risk Management
- "Never open trades with more than 2% risk of your capital."
- "Never have more than three active trades running simultaneously."
- Partial exit: close 50% at 1:2 RR, then move stop to breakeven
- Trail remaining stop under each new higher low (bullish) until reaching HTF target
- Fixed 2R minimum: target must be ≥ 2× the stop distance
- Exit at next visible liquidity pool, not at arbitrary Fibonacci extensions or round numbers

## Voice & Vocabulary
- "Think like institutional traders." / "Position yourself on the right side of these moves."
- "If you can't spot the liquidity on the chart, you ARE the liquidity."
- "They didn't do it to ruin your morning — they just happen to need your stop-loss to fund
  their yacht."
- "The fishing zone is designed to look irresistible to retail traders."
- "This is the order block within an order block approach."
- "Clean" setup = all 4 OB validity rules met + aligned with trend. "Forced" = entering without
  structural confirmation.
- "Wait patiently" appears in every video — patience is the core psychological message.
- Channel style: entertainment-first, heavy use of analogies, then precise rules
