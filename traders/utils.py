from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


def load_scanner(trader_dir: Path):
    """Load Scanner class from trader_dir/scanner.py without requiring a package."""
    spec = importlib.util.spec_from_file_location(
        f"_scanner_{trader_dir.name}",
        trader_dir / "scanner.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Scanner


def load_cfg(trader_dir: Path) -> dict:
    with open(trader_dir / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
