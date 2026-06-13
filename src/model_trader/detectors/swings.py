"""Swing high/low detector.

A swing high has lower highs on both sides; swing low has higher lows on both sides.
"""

from __future__ import annotations
from typing import TypedDict

from .base import Detector

class Swing(TypedDict):
    type: str      # 'high' or 'low'
    price: float
    index: int
    strength: int  # number of confirming candles on each side



class SwingDetector(Detector):
    name = "swing"

    def __init__(self, lookback: int = 3) -> None:
        self.lookback = lookback

    def detect(self, candles: list[dict]) -> list[Swing]:
        swings: list[Swing] = []

        for i in range(self.lookback, len(candles) - self.lookback):
            is_swing_high = all(
                candles[i]["high"] > candles[i - j]["high"]
                and candles[i]["high"] > candles[i + j]["high"]
                for j in range(1, self.lookback + 1)
            )

            is_swing_low = all(
                candles[i]["low"] < candles[i - j]["low"]
                and candles[i]["low"] < candles[i + j]["low"]
                for j in range(1, self.lookback + 1)
            )

            if is_swing_high:
                swings.append(
                    Swing(type="high", price=candles[i]["high"], index=i, strength=self.lookback)
                )
            if is_swing_low:
                swings.append(
                    Swing(type="low", price=candles[i]["low"], index=i, strength=self.lookback)
                )

        return swings

def detect_swings(candles: list[dict], lookback: int = 3) -> list[Swing]:
    return SwingDetector(lookback=lookback).detect(candles)
