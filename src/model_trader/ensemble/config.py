"""Ensemble configuration — YAML parsing, scanner definitions.

Loads an `ensemble:` section from a trader's config.yaml.
Each scanner is a COMPLETE trading strategy — not a single gate or detector.
Multiple scanners can use the same strategy module with different parameters,
or entirely different strategies.

Example:
    ensemble:
      scanners:
        - id: "ict_default"
          type: "champion"
          weight: 0.5
          strategy_module: "scanner"   # full strategy, uses config.yaml symbols/etc
          params: {{}}                 # kwargs passed to Scanner(config, data, **params)
        - id: "ict_loose"
          type: "challenger"
          weight: 0.25
          strategy_module: "scanner"
          params: {{"fvg_tolerance": 2.0}}  # same strategy, looser gates
        - id: "sd_zones"
          type: "challenger"
          weight: 0.25
          strategy_module: "scanner_supply_demand"  # completely different strategy
          params: {{}}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScannerDef:
    """Definition of one complete trading strategy in the ensemble.

    id               — stable identifier (used in DB)
    type             — "champion" or "challenger"
    weight           — voting weight (sum should ≤ 1.0)
    active           — False = skip this scanner on scan cycles
    strategy_module  — import path for the scanner class (e.g. "scanner")
    params           — kwargs passed to Scanner(config, data_adapter, **params)
    """

    id: str
    type: str = "challenger"
    weight: float = 0.25
    active: bool = True
    strategy_module: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.type not in ("champion", "challenger"):
            raise ValueError(f"Scanner type must be 'champion' or 'challenger', got '{self.type}'")


@dataclass
class EnsembleConfig:
    """Full ensemble configuration parsed from YAML.

    threshold             — min total weight to execute a trade (default 0.5)
    promotion_min_trades  — challenger needs ≥ N trades before eligible
    promotion_window_days — rolling window for max promotions check
    max_promotions_per_window — cap promotion churn
    db_path               — SQLite path for trade tracking
    scanners              — list of scanner definitions
    fallback_active       — set at runtime when degradation triggers
    """

    threshold: float = 0.5
    promotion_min_trades: int = 10
    promotion_window_days: int = 30
    max_promotions_per_window: int = 1
    db_path: str = "ensemble.db"
    scanners: list[ScannerDef] = field(default_factory=list)
    fallback_active: bool = field(default=False, repr=False)

    @property
    def active_scanners(self) -> list[ScannerDef]:
        return [s for s in self.scanners if s.active]

    @property
    def active_scanner_ids(self) -> set:
        return {s.id for s in self.active_scanners}

    def get_champion(self) -> ScannerDef | None:
        """Return the active champion, or None."""
        for s in self.active_scanners:
            if s.type == "champion":
                return s
        return None

    def active_challengers(self) -> list[ScannerDef]:
        return [
            s for s in self.active_scanners if s.type == "challenger"
        ]


def load_ensemble_config(config_dict: dict[str, Any]) -> EnsembleConfig:
    """Parse an `ensemble:` section from a YAML config dict.

    Example:
        ensemble:
          threshold: 0.5
          db_path: traders/my_trader/ensemble.db
          scanners:
            - id: "ict_default"
              type: "champion"
              weight: 0.5
              active: true
              strategy_module: "scanner"
              params: {{}}
            - id: "ict_loose"
              type: "challenger"
              weight: 0.25
              active: true
              strategy_module: "scanner"
              params: {{"fvg_tolerance": 2.0}}
    """
    ensemble_dict = config_dict.get("ensemble", {})
    if not ensemble_dict:
        raise ValueError("No 'ensemble:' section found in config")

    scanners_data = ensemble_dict.get("scanners", [])
    scanners = [
        ScannerDef(
            id=s["id"],
            type=s.get("type", "challenger"),
            weight=s.get("weight", 0.25),
            active=s.get("active", True),
            strategy_module=s.get("strategy_module", ""),
            params=s.get("params", s.get("config", {})),  # backward compat: config→params
        )
        for s in scanners_data
    ]

    return EnsembleConfig(
        threshold=ensemble_dict.get("threshold", 0.5),
        promotion_min_trades=ensemble_dict.get("promotion_min_trades", 10),
        promotion_window_days=ensemble_dict.get("promotion_window_days", 30),
        max_promotions_per_window=ensemble_dict.get(
            "max_promotions_per_window", 1
        ),
        db_path=ensemble_dict.get("db_path", "ensemble.db"),
        scanners=scanners,
    )
