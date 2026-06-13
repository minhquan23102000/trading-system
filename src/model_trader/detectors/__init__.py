"""Reusable price-action detectors — the building blocks every strategy uses.

Each detector is a class inheriting from Detector (see base.py). Detectors are
stateless after init — configure in __init__, call detect() or the instance
directly. Legacy function wrappers (detect_*) are kept for backward compat.
"""

from .base import Detector
from .fvg import FVGDetector, detect_fvg, update_fvg_states, FVG
from .swings import SwingDetector, detect_swings, Swing
from .failure_swings import FailureSwingDetector, detect_failure_swings, FailureSwing
from .cisd import CISDDetector, detect_cisd, detect_cisd_breaker, CISDSignal, Breaker
from .smt import SMTDetector, detect_smt, SMTSignal
from .displacement import DisplacementDetector, detect_displacement, Displacement

__all__ = [
    # base
    "Detector",
    # detector classes
    "FVGDetector",
    "SwingDetector",
    "FailureSwingDetector",
    "CISDDetector",
    "SMTDetector",
    "DisplacementDetector",
    # legacy functions
    "detect_fvg",
    "update_fvg_states",
    "detect_swings",
    "detect_failure_swings",
    "detect_cisd",
    "detect_cisd_breaker",
    "detect_smt",
    "detect_displacement",
    # types
    "FVG",
    "Swing",
    "FailureSwing",
    "CISDSignal",
    "Breaker",
    "SMTSignal",
    "Displacement",
]
