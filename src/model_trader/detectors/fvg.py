"""Fair Value Gap (FVG) detector.

A 3-candle pattern where candle 1's high doesn't overlap with candle 3's low
(bullish) or candle 1's low doesn't overlap with candle 3's high (bearish).
"""

from __future__ import annotations
from typing import TypedDict
from .base import Detector


class FVG(TypedDict):
    type: str          # 'bullish' or 'bearish'
    high: float        # upper bound of gap
    low: float         # lower bound of gap
    candle_index: int
    timestamp: str
    filled: bool
    inversed: bool
    respected: bool    # filled but then price reversed (gap tap + rejection)


class FVGDetector(Detector):
    name = "fvg"

    def detect(self, candles: list[dict]) -> list[FVG]:
        fvgs: list[FVG] = []
        for i in range(2, len(candles)):
            c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]

            if c1["high"] < c3["low"]:
                fvgs.append(
                    FVG(
                        type="bullish",
                        high=c3["low"],
                        low=c1["high"],
                        candle_index=i,
                        timestamp=c2.get("timestamp", ""),
                        filled=False,
                        inversed=False,
                        respected=False,
                    )
                )

            if c1["low"] > c3["high"]:
                fvgs.append(
                    FVG(
                        type="bearish",
                        high=c1["low"],
                        low=c3["high"],
                        candle_index=i,
                        timestamp=c2.get("timestamp", ""),
                        filled=False,
                        inversed=False,
                        respected=False,
                    )
                )

        return fvgs


def detect_fvg(candles: list[dict]) -> list[FVG]:
    return FVGDetector().detect(candles)


def update_fvg_states(fvgs: list[FVG], candles: list[dict]) -> list[FVG]:
    """Update filled/inversed/respected status of FVGs based on subsequent price action."""
    for fvg in fvgs:
        for candle in candles[fvg["candle_index"] + 1 :]:
            if fvg["type"] == "bullish":
                # Filled if price dips into the gap
                if candle["low"] <= fvg["high"]:
                    fvg["filled"] = True
                # Inversed if price sells through the gap completely
                if candle["close"] < fvg["low"]:
                    fvg["inversed"] = True
                    break
                # Respected if filled but then closed back above gap
                if fvg["filled"] and candle["close"] > fvg["high"]:
                    fvg["respected"] = True
            else:  # bearish
                if candle["high"] >= fvg["low"]:
                    fvg["filled"] = True
                if candle["close"] > fvg["high"]:
                    fvg["inversed"] = True
                    break
                # Respected if filled but then closed back below gap
                if fvg["filled"] and candle["close"] < fvg["low"]:
                    fvg["respected"] = True
    return fvgs
