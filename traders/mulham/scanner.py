"""Scanner for mulham.

Mulham's HTF key-level + LTF confirmation strategy.
Primary setup: 15-Minute Gold (Setup 3) — FVG continuation entry on a
High Probability Range, confirmed by 4H context and kill-zone timing.

Gate pipeline (10 gates):
  1  KILL_ZONE        — current time within Asia/London/NY session
  2  HTF_KEY_LEVEL    — nearest unfilled 4H FVG sets direction
  3  PRICE_POSITION   — price in discount (long ≤50%) or premium (short ≥50%)
  4  HP_RANGE         — 15m range: displaced ≥1.5×, filled ≥50%, anchored
  5  DIRECTION_ALIGN  — 4H candle bias vs. setup direction (reversal at-level OK)
  6  WEAKNESS_STRENGTH — failure-swing cluster + displacement in trade direction
  7  FVG_RESPECT      — direction-aligned 15m FVG: filled, not inversed
  8  ENTRY_TRIGGER    — 5m close-out candle through FVG boundary (WAIT if pending)
  9  RR_OK            — stop ≥0.20% of price, target ≥2:1 risk-reward
  10 FINAL            — set entry/stop/target/direction, status=TAKE

Data depth note: Hyperliquid API provides max 5,000 candles per timeframe.
The backtest steps on 15m (~52 days lookback); Gate 8 uses 5m for the trigger
candle when available, falls back to 15m otherwise. Live paper trading (main.py)
accumulates candles in memory — no API limit applies after initial fill.
"""

from __future__ import annotations

from datetime import datetime, timezone

from model_trader.gates import ScannerBase, SetupResult, SetupStatus
from model_trader.detectors import (
    SwingDetector,
    FVGDetector,
    FailureSwingDetector,
    DisplacementDetector,
    update_fvg_states,
)


class Scanner(ScannerBase):
    """Mulham — HTF key-level + LTF FVG continuation."""

    # Kill-zone hours in EST (UTC-5, no DST correction).
    # Each tuple is [start_inclusive, end_exclusive).
    _KILL_ZONES = [
        (20, 24),  # Asia:   20:00–00:00 EST
        (2,  5),   # London: 02:00–05:00 EST
        (7,  10),  # NY:     07:00–10:00 EST
    ]

    def __init__(self, config: dict, data_adapter) -> None:
        super().__init__(config, data_adapter)
        # Pre-instantiate stateless detectors; avoids per-call allocations.
        self._fvg = FVGDetector()
        self._swing = SwingDetector(lookback=3)
        self._disp = DisplacementDetector(lookback=10, threshold_multiplier=1.5)
        self._fail_swing = FailureSwingDetector(tolerance_pct=0.3)

    def evaluate(self, symbol: str) -> SetupResult:
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        data = self.fetch_data(symbol)
        corr_data = self.fetch_correlation(symbol, ["15m"])
        return self._run_gates(symbol, data, corr_data, ts=ts)

    def evaluate_at(
        self, symbol: str, hist: dict, corr_hist: dict, ts: int
    ) -> SetupResult:
        """Backtest variant: hist is pre-sliced by the runner; just delegate."""
        return self._run_gates(symbol, hist, corr_hist, ts=ts)

    # ------------------------------------------------------------------
    # Gate pipeline
    # ------------------------------------------------------------------

    def _run_gates(
        self, symbol: str, data: dict, corr_data: dict, ts: int
    ) -> SetupResult:
        result = SetupResult(symbol=symbol)

        # ===== GATE 1: KILL_ZONE =====
        dt_utc = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        est_h = (dt_utc.hour - 5) % 24  # EST = UTC-5, no DST

        in_kz = any(start <= est_h < end for start, end in self._KILL_ZONES)
        if not in_kz:
            result.reason = f"Outside kill zone (EST hour {est_h})"
            return result
        result.gates_passed.append("KILL_ZONE")

        # ===== Data checks =====
        candles_4h  = data.get("4h",  [])
        candles_15m = data.get("15m", [])
        candles_5m  = data.get("5m",  [])

        # 15m is the primary analysis timeframe — need enough for swings + FVGs.
        if len(candles_15m) < 30:
            result.reason = "Insufficient 15m history (<30 candles)"
            return result

        current_price = candles_15m[-1]["close"]

        def mid(fvg: dict) -> float:
            return (fvg["high"] + fvg["low"]) / 2.0

        # ===== GATE 2: HTF_KEY_LEVEL =====
        # An unfilled 4H FVG must exist; its type anchors direction.
        # Need ≥3 candles for FVGDetector (3-candle pattern).
        if len(candles_4h) < 3:
            result.reason = "Insufficient 4H data for HTF key level check (<3 candles)"
            return result

        recent_4h = candles_4h[-100:]
        fvgs_4h = self._fvg.detect(recent_4h)
        update_fvg_states(fvgs_4h, recent_4h)
        live_4h_fvgs = [f for f in fvgs_4h if not f["inversed"]]

        if not live_4h_fvgs:
            result.reason = "No active (unfilled) HTF 4H FVG in available candles"
            return result

        nearest_htf_fvg = min(
            live_4h_fvgs, key=lambda f: abs(current_price - mid(f))
        )
        direction = "short" if nearest_htf_fvg["type"] == "bearish" else "long"
        result.gates_passed.append("HTF_KEY_LEVEL")

        # ===== GATE 3: PRICE_POSITION =====
        # Use the most recent 15m swing range to compute fib zones.
        # Discount zone for longs (<=50%); premium zone for shorts (>=50%).
        swings_15m_full = self._swing.detect(candles_15m[-100:])
        highs_15m_rng = [s for s in swings_15m_full if s["type"] == "high"]
        lows_15m_rng  = [s for s in swings_15m_full if s["type"] == "low"]

        if not highs_15m_rng or not lows_15m_rng:
            result.reason = "Insufficient 15m swing structure for range"
            return result

        # Most recent coherent swing leg = last swing + the prior opposite-type
        # swing. Taking last high and last low independently produces a synthetic
        # range (non-contiguous legs); enforce a real bracketing pair.
        last_swing = swings_15m_full[-1]
        prior_opp = next(
            (s for s in reversed(swings_15m_full[:-1]) if s["type"] != last_swing["type"]),
            None,
        )
        if prior_opp is None:
            result.reason = "No coherent 15m swing leg (missing opposite swing)"
            return result
        if last_swing["type"] == "high":
            range_high, range_low = last_swing["price"], prior_opp["price"]
        else:
            range_high, range_low = prior_opp["price"], last_swing["price"]
        range_size = range_high - range_low

        if range_size <= 0:
            result.reason = "15m range has zero size (invalid swings)"
            return result

        range_mid_fib = range_low + 0.50 * range_size

        if direction == "long" and current_price > range_mid_fib:
            result.reason = (
                f"Price {current_price:.4f} above 50% mid {range_mid_fib:.4f}: "
                "not in discount zone for long"
            )
            return result
        if direction == "short" and current_price < range_mid_fib:
            result.reason = (
                f"Price {current_price:.4f} below 50% mid {range_mid_fib:.4f}: "
                "not in premium zone for short"
            )
            return result
        result.gates_passed.append("PRICE_POSITION")

        # ===== GATE 4: HP_RANGE =====
        # 15m range must satisfy: displaced (≥1.5×), filled (≥50%),
        # and anchored (base near a 4H FVG) — anchor check only if 4H
        # data is meaningful (≥10 candles).

        # Displaced: strong move in trade direction on recent 15m
        aligned_dir = "bullish" if direction == "long" else "bearish"
        disps_15m = self._disp.detect(candles_15m[-60:])
        aligned_disps = [d for d in disps_15m if d["direction"] == aligned_dir]

        if not aligned_disps:
            result.reason = (
                f"No {direction} displacement (≥1.5×) on 15m — BOS criterion not met"
            )
            return result

        # Filled: price has retraced ≥50% back into the range
        range_mid = (range_high + range_low) / 2.0
        if direction == "long" and current_price > range_mid:
            result.reason = (
                f"Range not filled ≥50% for long: price {current_price:.4f} "
                f"above 50% mid {range_mid:.4f}"
            )
            return result
        if direction == "short" and current_price < range_mid:
            result.reason = (
                f"Range not filled ≥50% for short: price {current_price:.4f} "
                f"below 50% mid {range_mid:.4f}"
            )
            return result

        # Anchored: range base overlaps with or is within 2% of a live 4H FVG.
        # Skip anchor check when 4H context is too shallow (<10 candles).
        if len(candles_4h) >= 10 and live_4h_fvgs:
            base_price = range_low if direction == "long" else range_high
            htf_near_base = any(
                f["low"] * 0.98 <= base_price <= f["high"] * 1.02
                for f in live_4h_fvgs
            )
            if not htf_near_base:
                result.reason = (
                    f"Range base {base_price:.4f} not anchored by any live 4H FVG"
                )
                return result

        result.gates_passed.append("HP_RANGE")

        # ===== GATE 5: DIRECTION_ALIGN =====
        # Direction should match the 4H candle bias unless price is
        # sitting directly at a recognised 4H key level (reversal acceptable).
        if len(candles_4h) >= 1:
            last_4h = candles_4h[-1]
            htf_bias = "long" if last_4h["close"] > last_4h["open"] else "short"

            at_htf_level = any(
                f["low"] * 0.99 <= current_price <= f["high"] * 1.01
                for f in live_4h_fvgs
            )
            if htf_bias != direction and not at_htf_level:
                result.reason = (
                    f"Direction {direction} opposes 4H candle bias ({htf_bias}) "
                    "and price is not at an HTF key level"
                )
                return result
        result.gates_passed.append("DIRECTION_ALIGN")

        # ===== GATE 6: WEAKNESS_STRENGTH =====
        # Weakness: failure-swing cluster on 15m (swings clustering at one level).
        # Strength: displacement candle in trade direction.
        swings_15m = self._swing.detect(candles_15m[-80:])
        failure_swings = self._fail_swing.detect(swings_15m)

        if not failure_swings:
            result.reason = "No failure-swing cluster (weakness) on 15m"
            return result

        disps_wide = self._disp.detect(candles_15m[-80:])
        strength_disps = [d for d in disps_wide if d["direction"] == aligned_dir]

        if not strength_disps:
            result.reason = (
                f"No {direction} displacement (strength) confirmed on 15m"
            )
            return result
        result.gates_passed.append("WEAKNESS_STRENGTH")

        # ===== GATE 7: FVG_RESPECT =====
        # Find a direction-aligned 15m FVG that price has touched (filled)
        # but not broken through (not inversed).
        recent_15m = candles_15m[-60:]
        fvgs_15m = self._fvg.detect(recent_15m)
        update_fvg_states(fvgs_15m, recent_15m)

        fvg_type = "bullish" if direction == "long" else "bearish"
        entry_fvgs = [
            f for f in fvgs_15m
            if f["type"] == fvg_type and f["filled"] and not f["inversed"]
        ]

        if not entry_fvgs:
            result.reason = (
                f"No respected (filled, not inversed) {fvg_type} 15m FVG at entry zone"
            )
            return result

        nearest_entry_fvg = min(
            entry_fvgs, key=lambda f: abs(current_price - mid(f))
        )
        result.gates_passed.append("FVG_RESPECT")

        # ===== GATE 8: ENTRY_TRIGGER =====
        # The close-out candle must close outside the FVG boundary in the
        # trade direction. Use 5m candle if available, else 15m.
        # Wrong-direction close-out → SKIP; no close-out yet → WAIT.
        ref = candles_5m[-1] if candles_5m else candles_15m[-1]

        if direction == "long":
            # Wrong direction: close breaks below FVG's lower edge
            if ref["close"] < nearest_entry_fvg["low"]:
                result.reason = (
                    "Close broke below bullish FVG lower edge (wrong direction)"
                )
                result.status = SetupStatus.SKIP
                return result
            trigger = ref["close"] > nearest_entry_fvg["high"]
        else:
            # Wrong direction: close breaks above FVG's upper edge
            if ref["close"] > nearest_entry_fvg["high"]:
                result.reason = (
                    "Close broke above bearish FVG upper edge (wrong direction)"
                )
                result.status = SetupStatus.SKIP
                return result
            trigger = ref["close"] < nearest_entry_fvg["low"]

        if not trigger:
            result.reason = (
                f"Waiting for {direction} close-out through 15m FVG "
                f"[{nearest_entry_fvg['low']:.4f}–{nearest_entry_fvg['high']:.4f}]"
            )
            result.status = SetupStatus.WAIT
            return result

        entry_price = ref["close"]
        result.gates_passed.append("ENTRY_TRIGGER")

        # ===== GATE 9: RR_OK =====
        # Stop just outside the FVG boundary (0.1% buffer).
        # Target model: "swing2r" (nearest structural swing beyond entry if
        # >=2R, else fixed 2R) or "htf_level" (next HTF 4H key level beyond
        # entry, fallback fixed 2R). Both fall back to fixed 2R when no
        # qualifying level exists, isolating the target choice from entries.
        target_model = self.config.get("target_model", "swing2r")
        highs_15m = [s for s in swings_15m if s["type"] == "high"]
        lows_15m  = [s for s in swings_15m if s["type"] == "low"]

        if direction == "long":
            stop = nearest_entry_fvg["low"] * (1 - 0.001)
            risk = entry_price - stop
            target = entry_price + risk * 2.0
            if target_model == "htf_level":
                cands = [f for f in live_4h_fvgs if f["low"] > entry_price]
                if cands:
                    target = min(c["low"] for c in cands)
            else:
                struct_highs = sorted(
                    [s for s in highs_15m if s["price"] > entry_price],
                    key=lambda s: s["price"],
                )
                if struct_highs:
                    candidate = struct_highs[0]["price"]
                    if (candidate - entry_price) >= risk * 2.0:
                        target = candidate
        else:
            stop = nearest_entry_fvg["high"] * (1 + 0.001)
            risk = stop - entry_price
            target = entry_price - risk * 2.0
            if target_model == "htf_level":
                cands = [f for f in live_4h_fvgs if f["high"] < entry_price]
                if cands:
                    target = max(c["high"] for c in cands)
            else:
                struct_lows = sorted(
                    [s for s in lows_15m if s["price"] < entry_price],
                    key=lambda s: s["price"],
                    reverse=True,
                )
                if struct_lows:
                    candidate = struct_lows[0]["price"]
                    if (entry_price - candidate) >= risk * 2.0:
                        target = candidate

        if risk <= 0:
            result.reason = "Zero or negative risk (stop == entry)"
            return result

        # Minimum stop distance: 0.20% of entry price.
        # Protects against noise-width FVG gaps in low-priced symbols (e.g. AVAX)
        # where sub-cent stops get eaten by normal spread/volatility.
        stop_pct = risk / entry_price
        if stop_pct < 0.0020:
            result.reason = (
                f"Stop distance {stop_pct*100:.2f}% too narrow (<0.20%): "
                "FVG gap is noise-width for this symbol"
            )
            return result

        actual_rr = abs(target - entry_price) / risk
        if actual_rr < 2.0:
            result.reason = f"RR {actual_rr:.2f} is below minimum 2:1"
            return result

        result.gates_passed.append("RR_OK")

        # ===== GATE 10: FINAL — set levels, mark TAKE =====
        result.entry = entry_price
        result.stop = stop
        result.target = target
        result.direction = direction
        result.status = SetupStatus.TAKE
        result.reason = "All gates passed"
        return result
