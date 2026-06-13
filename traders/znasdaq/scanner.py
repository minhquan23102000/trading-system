"""Scanner for znasdaq.

Z Nasdaq trades gold (XAUUSD) and Nasdaq (NQ) on a "draw on liquidity"
continuation model: find an untapped HTF draw, confirm it with SMT
divergence on a correlated pair, then enter on a 15m/5m FVG tap +
inversion/CISD breaker with a 1:1R target and a structural stop.

Gate pipeline (6 gates, see strategy.md "Gates (Draft Pipeline)"):
  1  HTF_BIAS        — 4h displacement establishes continuation direction
  2  QUALIFIED_DOL   — untapped failure-swing / weak-swing / 4h FVG draw in
                        bias direction, with no equal-strength competing draw
  3  SMT_CONFIRM     — SMT divergence vs. correlated symbol on 1h swings
  4  ENTRY_ZONE      — 15m FVG tap + inversion, or CISD breaker, in direction
  5  PROTECTED_STOP  — structural invalidation level within ~2x 15m ATR
  6  FINAL           — set entry/stop/target/direction, status=TAKE

See docs/designing-gates.md for guidance on how to translate a strategy
document into gate logic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from model_trader.gates import ScannerBase, SetupResult, SetupStatus
from model_trader.detectors import (
    SwingDetector,
    FVGDetector,
    FailureSwingDetector,
    CISDDetector,
    SMTDetector,
    DisplacementDetector,
    update_fvg_states,
    detect_cisd_breaker,
)


class Scanner(ScannerBase):
    """Z Nasdaq — HTF draw on liquidity + SMT + 15m FVG continuation."""

    def __init__(self, config: dict, data_adapter) -> None:
        super().__init__(config, data_adapter)
        self.swing = SwingDetector(lookback=2)
        self.fvg = FVGDetector()
        self.failure_swing = FailureSwingDetector(tolerance_pct=0.15)
        self.cisd = CISDDetector()
        self.smt = SMTDetector()
        self.displacement = DisplacementDetector(lookback=3, threshold_multiplier=1.5)

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def evaluate(self, symbol: str) -> SetupResult:
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        data = self.fetch_data(symbol)
        corr_data = self.fetch_correlation(symbol, self.timeframes)
        return self._run_gates(symbol, data, corr_data, ts)

    def evaluate_at(self, symbol: str, hist: dict, corr_hist: dict, ts: int) -> SetupResult:
        """Backtest variant: slice hist to ts before running gates."""
        filtered = {
            tf: [c for c in candles if c["timestamp"] <= ts]
            for tf, candles in hist.items()
        }
        filtered_corr = {
            tf: [c for c in candles if c["timestamp"] <= ts]
            for tf, candles in corr_hist.items()
        }
        return self._run_gates(symbol, filtered, filtered_corr, ts)

    # ------------------------------------------------------------------
    # Gate pipeline
    # ------------------------------------------------------------------

    def _run_gates(self, symbol: str, data: dict, corr_data: dict, ts: int) -> SetupResult:
        result = SetupResult(symbol=symbol)

        c4h = data.get("4h", [])
        c1h = data.get("1h", [])
        c15m = data.get("15m", [])
        c5m = data.get("5m", [])

        if len(c4h) < 10 or len(c1h) < 10 or len(c15m) < 10 or len(c5m) < 1:
            result.reason = "Insufficient candle history"
            return result

        current_price = c5m[-1]["close"]

        # ===== GATE 1: HTF_BIAS =====
        # A recent 4h displacement establishes the continuation direction.
        disp_4h = self.displacement.detect(c4h)
        if not disp_4h:
            result.reason = "No 4h displacement - no clear HTF bias"
            return result
        direction = "long" if disp_4h[-1]["direction"] == "bullish" else "short"
        result.gates_passed.append("HTF_BIAS")

        # ===== GATE 2: QUALIFIED_DOL =====
        # An untapped draw (failure swing, weak swing, or unfilled 4h FVG)
        # must sit in the bias direction, with no equal-strength competitor
        # in the opposite direction.
        swings_1h = self.swing.detect(c1h)
        fail_swings_1h = self.failure_swing.detect(swings_1h)
        fvgs_4h = self.fvg.detect(c4h)
        update_fvg_states(fvgs_4h, c4h)

        draw_level, draw_dist = self._nearest_draw(
            direction, current_price, swings_1h, fail_swings_1h, fvgs_4h
        )
        if draw_level is None:
            result.reason = f"No qualified draw on liquidity for {direction} bias"
            return result

        opposite = "short" if direction == "long" else "long"
        _, competing_dist = self._nearest_draw(
            opposite, current_price, swings_1h, fail_swings_1h, fvgs_4h
        )
        if competing_dist is not None and competing_dist <= draw_dist * 1.2:
            result.reason = "Competing draw of equal strength in opposite direction"
            return result

        result.extras["draw_level"] = draw_level
        result.gates_passed.append("QUALIFIED_DOL")

        # ===== GATE 3: SMT_CONFIRM =====
        # SMT divergence vs. the correlated symbol on 1h swing extremes.
        corr_1h = corr_data.get("1h", [])
        if len(corr_1h) < 10:
            result.reason = "No correlated-symbol data for SMT"
            return result
        corr_swings_1h = self.swing.detect(corr_1h)
        smt_signals = self.smt.detect(swings_1h, corr_swings_1h)
        want_smt = "bullish" if direction == "long" else "bearish"
        if not any(s["type"] == want_smt for s in smt_signals):
            result.reason = f"No {want_smt} SMT confirmation on 1h"
            return result
        result.gates_passed.append("SMT_CONFIRM")

        # ===== GATE 4: ENTRY_ZONE =====
        # 15m FVG tapped with an inversion/respect, or a CISD breaker, in
        # the bias direction.
        fvgs_15m = self.fvg.detect(c15m)
        update_fvg_states(fvgs_15m, c15m)
        want_fvg = "bullish" if direction == "long" else "bearish"
        tapped = [
            f for f in fvgs_15m
            if f["type"] == want_fvg and f["filled"] and (f["inversed"] or f["respected"])
        ]

        swings_15m = self.swing.detect(c15m)
        cisd_signals = self.cisd.detect(c15m, swings_15m)
        breaker = None
        for sig in cisd_signals:
            if sig["type"] == want_smt:
                breaker = detect_cisd_breaker(c15m, sig)
                break

        if not tapped and not breaker:
            result.status = SetupStatus.WAIT
            result.reason = (
                f"No 15m {want_fvg} FVG tap with inversion and no CISD breaker yet"
            )
            return result
        result.gates_passed.append("ENTRY_ZONE")

        # ===== GATE 5: PROTECTED_STOP =====
        # Stop at the 4h swing extreme that the displacement originated
        # from, or the FVG/breaker boundary if that's tighter, checked
        # against ~2x the 15m ATR.
        swings_4h = self.swing.detect(c4h)
        structural_type = "low" if direction == "long" else "high"
        structural_swings = [s for s in swings_4h if s["type"] == structural_type]
        if not structural_swings:
            result.reason = "No structural 4h swing for protected stop"
            return result
        structural_stop = structural_swings[-1]["price"]

        tight_candidates = [structural_stop]
        if tapped:
            tight_candidates.append(tapped[-1]["low"] if direction == "long" else tapped[-1]["high"])
        elif breaker:
            tight_candidates.append(breaker["low"] if direction == "long" else breaker["high"])

        if direction == "long":
            valid = [c for c in tight_candidates if c < current_price]
            stop_price = max(valid) if valid else structural_stop
        else:
            valid = [c for c in tight_candidates if c > current_price]
            stop_price = min(valid) if valid else structural_stop

        atr_15m = sum(c["high"] - c["low"] for c in c15m[-14:]) / min(14, len(c15m))
        stop_dist = abs(current_price - stop_price)
        if atr_15m <= 0 or stop_dist <= 0 or stop_dist > 2 * atr_15m * 14:
            result.reason = "No reasonable structural invalidation (stop too far from ATR)"
            return result
        result.gates_passed.append("PROTECTED_STOP")

        # ===== GATE 6 (FINAL): set entry/stop/target, TAKE =====
        entry_price = c15m[-1]["close"]
        risk = abs(entry_price - stop_price)
        target_price = entry_price + risk if direction == "long" else entry_price - risk

        result.direction = direction
        result.entry = entry_price
        result.stop = stop_price
        result.target = target_price
        result.status = SetupStatus.TAKE
        result.reason = "All gates passed"
        result.gates_passed.append("FINAL")
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _nearest_draw(
        self,
        direction: str,
        current_price: float,
        swings_1h: list[dict],
        fail_swings_1h: list[dict],
        fvgs_4h: list[dict],
    ) -> tuple[float | None, float | None]:
        """Return (level, distance) of the nearest untapped draw above/below
        `current_price` for `direction`, or (None, None) if none qualifies.

        Candidates (per strategy.md "Draw on Liquidity"):
          - failure swing clusters on the relevant side
          - the most recent un-swept ("weak") swing high/low
          - unfilled 4h FVGs on the relevant side
        """
        levels: list[float] = []

        if direction == "long":
            levels += [fs["level"] for fs in fail_swings_1h if fs["type"] == "high" and fs["level"] > current_price]
            highs = [s for s in swings_1h if s["type"] == "high"]
            if highs and highs[-1]["price"] > current_price:
                levels.append(highs[-1]["price"])
            levels += [
                f["low"] for f in fvgs_4h
                if f["type"] == "bullish" and not f["filled"] and f["low"] > current_price
            ]
        else:
            levels += [fs["level"] for fs in fail_swings_1h if fs["type"] == "low" and fs["level"] < current_price]
            lows = [s for s in swings_1h if s["type"] == "low"]
            if lows and lows[-1]["price"] < current_price:
                levels.append(lows[-1]["price"])
            levels += [
                f["high"] for f in fvgs_4h
                if f["type"] == "bearish" and not f["filled"] and f["high"] < current_price
            ]

        if not levels:
            return None, None

        level = min(levels) if direction == "long" else max(levels)
        return level, abs(level - current_price)
