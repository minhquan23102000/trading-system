"""Composite scoring engine for per-scanner ranking.

Formula: composite = profit_factor × ln(1 + trade_count) × stability_bonus

- profit_factor: gross_win / abs(gross_loss), clipped to [0, 10]
- trade_count: total closed trades in window
- stability_bonus: 1.15 if profit_factor > 1.2 in two consecutive windows, else 1.0
"""

from __future__ import annotations

import math

from .db import EnsembleDB


class ScoreEngine:
    """Compute composite scores and rank scanners."""

    def __init__(self, db: EnsembleDB, window_days: int = 30):
        self._db = db
        self.window_days = window_days

    def compute(self, scanner_id: str) -> dict:
        """Return score components + composite for one scanner."""
        stats = self._db.get_scanner_stats(scanner_id, self.window_days)
        pf = self._profit_factor(stats)
        count = stats.get("trade_count", 0) or 0
        stability = self._stability_bonus(scanner_id, pf)
        composite = self._composite(pf, count, stability)
        return {
            "scanner_id": scanner_id,
            "profit_factor": pf,
            "trade_count": count,
            "stability_bonus": stability,
            "composite": composite,
            "wins": stats.get("wins", 0) or 0,
            "losses": stats.get("losses", 0) or 0,
            "total_pnl": stats.get("total_pnl", 0) or 0,
            "avg_r": stats.get("avg_r", 0.0) or 0.0,
        }

    def rank_all(self, scanner_ids: list[str]) -> list[dict]:
        """Return scanner scores sorted by composite descending."""
        scores = [self.compute(sid) for sid in scanner_ids]
        scores.sort(key=lambda s: s["composite"], reverse=True)
        return scores

    def _profit_factor(self, stats: dict) -> float:
        gross_win = stats.get("gross_win", 0) or 0
        gross_loss = abs(stats.get("gross_loss", 0) or 0)
        if gross_loss == 0:
            return 10.0 if gross_win > 0 else 1.0
        pf = gross_win / gross_loss
        return min(pf, 10.0)

    def _stability_bonus(self, scanner_id: str, current_pf: float) -> float:
        """1.15 if PF > 1.2 in current AND prior window, else 1.0."""
        if current_pf < 1.2:
            return 1.0
        # Check prior window
        prior = self._db.get_scanner_stats(scanner_id, self.window_days * 2)
        if prior.get("trade_count", 0) < 2:
            return 1.0
        prior_gross_win = prior.get("gross_win", 0) or 0
        prior_gross_loss = abs(prior.get("gross_loss", 0) or 0)
        if prior_gross_loss == 0:
            prior_pf = 10.0 if prior_gross_win > 0 else 1.0
        else:
            prior_pf = prior_gross_win / prior_gross_loss
        return 1.15 if prior_pf > 1.2 else 1.0

    def _composite(self, pf: float, count: int, stability: float) -> float:
        return pf * math.log(1 + count) * stability
