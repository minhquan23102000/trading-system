"""Scanner for tradingnotes.

Implements the SMC Multi-Timeframe setup as a 7-gate pipeline:
  1. 1H trend direction — clear HH/HL (long) or LH/LL (short) structure
  2. 1H unmitigated FVG — aligned with trend, inducement-filtered
  3. Daily context space — no major daily swing blocking the target direction
  4. Price at/near 1H FVG — retrace has reached the zone (within 0.5% tolerance)
  5. 5M liquidity grab — V-shape sweep of swing low (long) or swing high (short)
  6. 5M CHoCH — body close above swing high (long) or below swing low (short)
  7. Levels → TAKE — entry at 5M OB, stop beyond sweep extreme, target next 1H swing

Both long and short setups are active. See strategy.md for the full gate spec.
"""

from __future__ import annotations

from model_trader.gates import ScannerBase, SetupResult, SetupStatus
from model_trader.detectors import (
    SwingDetector,
    FVGDetector,
    update_fvg_states,
)


class Scanner(ScannerBase):
    """Trading Notes SMC Multi-Timeframe scanner — long and short setups."""

    # Risk:reward cap. Targets farther than this multiple of stop distance are
    # clipped to entry ± MAX_RR × risk. Calibrated from backtest: 3 of 4 losers
    # had planned RR > 3.0 (distant 1H swings rarely fill before chop hits stop).
    MAX_RR = 3.0

    def __init__(self, config: dict, data_adapter) -> None:
        super().__init__(config, data_adapter)
        self._swing1h = SwingDetector(lookback=3)
        self._swing1d = SwingDetector(lookback=3)
        self._swing5m = SwingDetector(lookback=2)
        self._fvg = FVGDetector()

    # ------------------------------------------------------------------
    # Core gate pipeline (shared by evaluate() and evaluate_at())
    # ------------------------------------------------------------------

    def _run_gates(self, symbol: str, data: dict, corr_data: dict) -> SetupResult:
        result = SetupResult(symbol=symbol)

        # ===== GATE 1: 1H trend direction =====
        candles_1h = data.get("1h", [])[-60:]
        if len(candles_1h) < 20:
            result.reason = "Insufficient 1H history (need 20+ candles)"
            return result

        swings_1h = self._swing1h.detect(candles_1h)
        if len(swings_1h) < 4:
            result.reason = f"Not enough 1H swings ({len(swings_1h)}), need 4+ for structure"
            return result

        # Use last 4 swings minimum; check only the two most recent highs and lows
        # (most recent pair is what the trader actually looks at, not full history)
        recent = swings_1h[-6:]
        highs = [s for s in recent if s["type"] == "high"]
        lows = [s for s in recent if s["type"] == "low"]

        if len(highs) < 2 or len(lows) < 2:
            result.reason = "Not enough alternating swing highs/lows on 1H"
            return result

        # Only the last 2 of each type: HH (h2 > h1) + HL (l2 > l1) = bullish
        last_h1, last_h2 = highs[-2]["price"], highs[-1]["price"]
        last_l1, last_l2 = lows[-2]["price"], lows[-1]["price"]

        is_bullish = last_h2 > last_h1 and last_l2 > last_l1
        is_bearish = last_h2 < last_h1 and last_l2 < last_l1

        if not is_bullish and not is_bearish:
            result.reason = "1H structure mixed/consolidating — no clear HH/HL or LH/LL"
            return result

        direction = "long" if is_bullish else "short"
        result.extras["direction"] = direction

        # Both directions are now handled; fall through to Gate 2.

        result.gates_passed.append("1H_TREND")

        # ===== GATE 2: 1H unmitigated FVG (bullish, below current price) =====
        fvgs_1h = self._fvg.detect(candles_1h)
        update_fvg_states(fvgs_1h, candles_1h)

        current_price = candles_1h[-1]["close"]

        # Long: bullish FVG below price (demand zone; price pulls back into it)
        # Short: bearish FVG above price (supply zone; price rallies back into it)
        # Inducement rule: if another unmitigated same-type FVG exists beyond the candidate
        # (i.e. further from price), the nearer candidate is a trap — use the farther one.
        if direction == "long":
            fvg_type = "bullish"
            candidates = [
                f for f in fvgs_1h
                if f["type"] == fvg_type
                and not f["inversed"]
                and f["high"] < current_price
            ]
            # Sort ascending by high → lowest zone first = furthest from price = no trap below it
            candidates.sort(key=lambda f: f["high"])
        else:
            fvg_type = "bearish"
            candidates = [
                f for f in fvgs_1h
                if f["type"] == fvg_type
                and not f["inversed"]
                and f["low"] > current_price
            ]
            # Sort descending by low → highest zone first = furthest from price = no trap above it
            candidates.sort(key=lambda f: f["low"], reverse=True)

        if not candidates:
            result.reason = (
                f"No unmitigated {fvg_type} 1H FVG "
                f"{'below' if direction == 'long' else 'above'} current price"
            )
            return result

        htf_fvg = candidates[0]
        result.extras["htf_fvg"] = htf_fvg
        result.gates_passed.append("1H_FVG")

        # ===== GATE 3: Daily context space clear =====
        candles_1d = data.get("1d", [])[-30:]
        if len(candles_1d) >= 5:
            swings_1d = self._swing1d.detect(candles_1d)
            if direction == "long":
                # Need clear overhead space — no daily swing high within 0.5%
                blocking = [
                    s for s in swings_1d
                    if s["type"] == "high" and s["price"] > current_price
                ]
                blocking.sort(key=lambda s: s["price"])  # nearest first
                if blocking:
                    nearest = blocking[0]["price"]
                    if (nearest - current_price) / current_price < 0.005:
                        result.reason = (
                            f"Daily swing high {nearest:.2f} within 0.5% overhead "
                            f"(current {current_price:.2f}) — no room to run"
                        )
                        return result
            else:
                # Short: need clear space below — no daily swing low within 0.5%
                blocking = [
                    s for s in swings_1d
                    if s["type"] == "low" and s["price"] < current_price
                ]
                blocking.sort(key=lambda s: s["price"], reverse=True)  # nearest first
                if blocking:
                    nearest = blocking[0]["price"]
                    if (current_price - nearest) / current_price < 0.005:
                        result.reason = (
                            f"Daily swing low {nearest:.2f} within 0.5% below "
                            f"current {current_price:.2f} — no room to run"
                        )
                        return result
            result.gates_passed.append("DAILY_SPACE")
        else:
            result.gates_passed.append("DAILY_SPACE_SKIP")

        # ===== GATE 4: Price at/near the 1H FVG zone =====
        fvg_top = htf_fvg["high"]    # upper bound of gap
        fvg_bottom = htf_fvg["low"]  # lower bound of gap
        tolerance = fvg_top * 0.005  # 0.5% window

        if direction == "long":
            # Price should be inside [fvg_bottom, fvg_top + tolerance]
            if current_price < fvg_bottom:
                result.reason = (
                    f"Price {current_price:.2f} below FVG bottom {fvg_bottom:.2f} — "
                    "pullback overshot"
                )
                return result
            if current_price > fvg_top + tolerance:
                result.reason = (
                    f"Price {current_price:.2f} above FVG top {fvg_top:.2f} + 0.5% — "
                    "pullback not yet reached"
                )
                return result
        else:
            # Short: bearish FVG is above price; rally should have reached FVG bottom
            bear_tolerance = fvg_bottom * 0.005
            if current_price > fvg_top:
                result.reason = (
                    f"Price {current_price:.2f} above FVG top {fvg_top:.2f} — "
                    "rally overshot FVG"
                )
                return result
            if current_price < fvg_bottom - bear_tolerance:
                result.reason = (
                    f"Price {current_price:.2f} below FVG bottom {fvg_bottom:.2f} - 0.5% — "
                    "rally not yet reached FVG"
                )
                return result

        result.gates_passed.append("PRICE_AT_FVG")

        # ===== GATE 5: 5M liquidity grab =====
        candles_5m = data.get("5m", [])[-40:]
        if len(candles_5m) < 10:
            result.reason = "Insufficient 5M candles for liquidity grab detection"
            return result

        swings_5m = self._swing5m.detect(candles_5m)
        n5 = len(candles_5m)

        sweep_candle_idx: int | None = None
        sweep_extreme: float | None = None  # sweep low (long) or sweep high (short)

        if direction == "long":
            # Look for V-shape: wick below recent swing low, body closes back above
            swing_lows_5m = [
                s for s in swings_5m
                if s["type"] == "low" and s["index"] >= n5 - 25
            ]
            for sl in reversed(swing_lows_5m):
                sl_price = sl["price"]
                start = max(sl["index"] + 1, n5 - 25)
                for ci in range(start, n5):
                    c = candles_5m[ci]
                    if c["low"] < sl_price and c["close"] > sl_price:
                        sweep_candle_idx = ci
                        sweep_extreme = c["low"]
                        break
                if sweep_candle_idx is not None:
                    break
            if sweep_candle_idx is None:
                result.reason = "No 5M bullish liquidity grab (V-shape sweep below swing low) in last 25 bars"
                return result
            result.extras["sweep_low"] = sweep_extreme
        else:
            # Look for inverted V: wick above recent swing high, body closes back below
            swing_highs_5m = [
                s for s in swings_5m
                if s["type"] == "high" and s["index"] >= n5 - 25
            ]
            for sh in reversed(swing_highs_5m):
                sh_price = sh["price"]
                start = max(sh["index"] + 1, n5 - 25)
                for ci in range(start, n5):
                    c = candles_5m[ci]
                    if c["high"] > sh_price and c["close"] < sh_price:
                        sweep_candle_idx = ci
                        sweep_extreme = c["high"]
                        break
                if sweep_candle_idx is not None:
                    break
            if sweep_candle_idx is None:
                result.reason = "No 5M bearish liquidity grab (inverted V above swing high) in last 25 bars"
                return result
            result.extras["sweep_high"] = sweep_extreme

        result.extras["sweep_candle_idx"] = sweep_candle_idx
        result.gates_passed.append("5M_LIQ_GRAB")

        # ===== GATE 6: 5M structural shift (CHoCH) =====
        choch_candle_idx: int | None = None

        if direction == "long":
            # Most recent swing HIGH before sweep → body must close above it after sweep
            refs_before = [
                s for s in swings_5m
                if s["type"] == "high" and s["index"] < sweep_candle_idx
            ]
            if not refs_before:
                result.reason = "No 5M swing high before liquidity grab to anchor bullish CHoCH"
                return result
            ref = max(refs_before, key=lambda s: s["index"])
            choch_level = ref["price"]
            for ci in range(sweep_candle_idx + 1, n5):
                if candles_5m[ci]["close"] > choch_level:
                    choch_candle_idx = ci
                    break
            if choch_candle_idx is None:
                result.reason = (
                    f"No 5M bullish CHoCH: no close above {choch_level:.2f} after sweep"
                )
                return result
        else:
            # Short: most recent swing LOW before sweep → body must close below it after sweep
            refs_before = [
                s for s in swings_5m
                if s["type"] == "low" and s["index"] < sweep_candle_idx
            ]
            if not refs_before:
                result.reason = "No 5M swing low before liquidity grab to anchor bearish CHoCH"
                return result
            ref = max(refs_before, key=lambda s: s["index"])
            choch_level = ref["price"]
            for ci in range(sweep_candle_idx + 1, n5):
                if candles_5m[ci]["close"] < choch_level:
                    choch_candle_idx = ci
                    break
            if choch_candle_idx is None:
                result.reason = (
                    f"No 5M bearish CHoCH: no close below {choch_level:.2f} after sweep"
                )
                return result

        result.extras["choch_level"] = choch_level
        result.gates_passed.append("5M_CHOCH")

        # ===== GATE 7 (FINAL): Compute levels → TAKE =====
        if direction == "long":
            # Entry: HIGH of last bearish 5M candle before CHoCH (5M demand OB)
            ob_entry: float | None = None
            for ci in range(choch_candle_idx - 1, max(sweep_candle_idx - 1, -1), -1):
                c = candles_5m[ci]
                if c["close"] < c["open"]:  # bearish
                    ob_entry = c["high"]
                    break
            if ob_entry is None:
                ob_entry = candles_5m[sweep_candle_idx]["high"]

            stop = sweep_extreme * (1.0 - 0.0005)  # just below sweep low

            # Target: nearest 1H swing HIGH above current price
            swing_highs_1h_above = [
                s for s in swings_1h
                if s["type"] == "high" and s["price"] > current_price
            ]
            if not swing_highs_1h_above:
                result.reason = "No 1H swing high above current price for long target"
                return result
            swing_highs_1h_above.sort(key=lambda s: s["price"])
            raw_target = swing_highs_1h_above[0]["price"]

            risk = ob_entry - stop
            # Cap target at MAX_RR × risk to avoid distant-swing chop-out
            target = min(raw_target, ob_entry + self.MAX_RR * risk)
            reward = target - ob_entry

        else:
            # Entry: LOW of last bullish 5M candle before bearish CHoCH (5M supply OB)
            ob_entry = None
            for ci in range(choch_candle_idx - 1, max(sweep_candle_idx - 1, -1), -1):
                c = candles_5m[ci]
                if c["close"] > c["open"]:  # bullish
                    ob_entry = c["low"]
                    break
            if ob_entry is None:
                ob_entry = candles_5m[sweep_candle_idx]["low"]

            stop = sweep_extreme * (1.0 + 0.0005)  # just above sweep high

            # Target: nearest 1H swing LOW below current price
            swing_lows_1h_below = [
                s for s in swings_1h
                if s["type"] == "low" and s["price"] < current_price
            ]
            if not swing_lows_1h_below:
                result.reason = "No 1H swing low below current price for short target"
                return result
            swing_lows_1h_below.sort(key=lambda s: s["price"], reverse=True)
            raw_target = swing_lows_1h_below[0]["price"]

            risk = stop - ob_entry
            # Cap target at MAX_RR × risk
            target = max(raw_target, ob_entry - self.MAX_RR * risk)
            reward = ob_entry - target

        if risk <= 0 or reward <= 0:
            result.reason = (
                f"Invalid levels — entry={ob_entry:.2f} stop={stop:.2f} "
                f"target={target:.2f} (risk={risk:.4f} reward={reward:.4f})"
            )
            return result

        result.entry = ob_entry
        result.stop = stop
        result.target = target
        result.direction = direction
        result.status = SetupStatus.TAKE
        result.reason = f"All gates passed — SMC {direction} setup confirmed"
        result.gates_passed.append("LEVELS_SET")
        return result

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate(self, symbol: str) -> SetupResult:
        data = self.fetch_data(symbol)
        corr_data = self.fetch_correlation(symbol, [])
        return self._run_gates(symbol, data, corr_data)

    def evaluate_at(self, symbol: str, hist: dict, corr_hist: dict, ts: int) -> SetupResult:
        """Backtest variant: hist is pre-sliced by the runner; just delegate."""
        return self._run_gates(symbol, hist, corr_hist)
