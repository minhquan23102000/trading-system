"""model-trader: turn a trader's content into an executable screener and paper trader."""

__version__ = "0.1.0"

from .data import DataAdapter, HyperliquidAdapter
from .detectors import (
    Detector,
    SwingDetector,
    FVGDetector,
    FailureSwingDetector,
    CISDDetector,
    SMTDetector,
    DisplacementDetector,
    detect_swings,
    detect_fvg,
    detect_failure_swings,
    detect_cisd,
    detect_smt,
    detect_displacement,
)
from .gates import ScannerBase, SetupResult, SetupStatus
from .paper_trader import PaperTrader
from .monitor import run_monitor
from .portfolio import PortfolioOrchestrator
from .ensemble import (
    EnsembleDB,
    ScoreEngine,
    DegradationDetector,
    EnsembleEngine,
    EnsembleConfig,
    ScannerDef,
    load_ensemble_config,
)

__all__ = [
    "DataAdapter",
    "HyperliquidAdapter",
    "ScannerBase",
    "SetupResult",
    "SetupStatus",
    "PaperTrader",
    "run_monitor",
    "PortfolioOrchestrator",
    "EnsembleDB",
    "ScoreEngine",
    "DegradationDetector",
    "EnsembleEngine",
    "EnsembleConfig",
    "ScannerDef",
    "load_ensemble_config",
    "Detector",
    "SwingDetector",
    "FVGDetector",
    "FailureSwingDetector",
    "CISDDetector",
    "SMTDetector",
    "DisplacementDetector",
    "detect_swings",
    "detect_fvg",
    "detect_failure_swings",
    "detect_cisd",
    "detect_smt",
    "detect_displacement",
]
