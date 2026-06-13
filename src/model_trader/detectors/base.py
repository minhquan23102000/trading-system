"""Detector base class.

All market structure detectors inherit from Detector. Each detector:
- Accepts configuration in __init__ (no mutable state after init)
- Implements detect() returning a list of typed event dicts
- Is callable: instance(candles) → detect(candles)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Detector(ABC):
    """Base class for price-action / market-structure detectors.

    Subclass and set `name` to a unique lowercase identifier. Implement
    `detect()` with the detector-specific arguments and return type.

    Usage:
        detector = SwingDetector(lookback=5)
        swings = detector.detect(candles)
        # or: detector(candles)
    """

    name: str = ""

    @abstractmethod
    def detect(self, **kwargs: Any) -> list[dict]:
        """Run detection. Input kwargs depend on detector type."""
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> list[dict]:
        """Convenience: instance(args) delegates to detect(args)."""
        return self.detect(*args, **kwargs)
