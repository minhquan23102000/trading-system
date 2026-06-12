"""Ensemble voting system — champion-challenger with weighted voting.

Replaces the removed agent layer. Scanners vote on setups; the ensemble
engine collects votes, runs degradation checks, and promotes challengers.

Exports:
    EnsembleDB            — SQLite trade/perf tracking
    ScoreEngine           — composite scoring
    DegradationDetector   — correlation + drag detection
    EnsembleEngine        — weighted voting engine
    EnsembleConfig        — YAML config dataclass
    ScannerDef            — individual scanner definition
    load_ensemble_config  — config parser
"""

from .db import EnsembleDB
from .scoring import ScoreEngine
from .degradation import DegradationDetector
from .engine import EnsembleEngine
from .config import EnsembleConfig, ScannerDef, load_ensemble_config

__all__ = [
    "EnsembleDB",
    "ScoreEngine",
    "DegradationDetector",
    "EnsembleEngine",
    "EnsembleConfig",
    "ScannerDef",
    "load_ensemble_config",
]
