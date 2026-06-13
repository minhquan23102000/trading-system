"""Displacement detector.

Identifies strong, aggressive price moves (candles significantly larger than average).
"""

from __future__ import annotations
from typing import TypedDict

from .base import Detector




class Displacement(TypedDict):
    index: int
    direction: str   # 'bullish' or 'bearish'
    size_ratio: float




class DisplacementDetector(Detector):
    name = "displacement"

    def __init__(self, lookback: int = 5, threshold_multiplier: float = 2.0):
        self.lookback = lookback
        self.threshold_multiplier = threshold_multiplier

    def detect(self, candles: list[dict]) -> list[Displacement]:
        sizes = [abs(c["close"] - c["open"]) for c in candles[-self.lookback * 3 : -self.lookback]]
        avg_size = sum(sizes) / len(sizes) if sizes else 0

        displacements: list[Displacement] = []
        for i, c in enumerate(candles[-self.lookback:]):
            size = abs(c["close"] - c["open"])
            if avg_size > 0 and size > avg_size * self.threshold_multiplier:
                displacements.append(
                    Displacement(
                        index=len(candles) - self.lookback + i,
                        direction="bullish" if c["close"] > c["open"] else "bearish",
                        size_ratio=size / avg_size,
                    )
                )

        return displacements


def detect_displacement(
    candles: list[dict], lookback: int = 5, threshold_multiplier: float = 2.0
) -> list[Displacement]:
    return DisplacementDetector(
        lookback=lookback, threshold_multiplier=threshold_multiplier
    ).detect(candles)
