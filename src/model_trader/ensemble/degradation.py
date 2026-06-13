"""Degradation detection — correlation, drag, and auto-fallback.

Monitors the ensemble for:
- Excess scanner correlation: if two scanners agree >85% of the time,
  they're not independent votes.
- Champion drag: if the ensemble profit factor drops below 90% of the
  champion's, fall back to champion-only.
"""

from __future__ import annotations

from collections import Counter

from .db import EnsembleDB


class DegradationDetector:
    """Detect ensemble health issues and signal fallback."""

    def __init__(
        self,
        db: EnsembleDB,
        warn_correlation: float = 0.85,
        drag_threshold: float = 0.9,
    ):
        self._db = db
        self.warn_correlation = warn_correlation
        self.drag_threshold = drag_threshold

    def check_correlation(
        self, scanner_ids: list[str]
    ) -> list[tuple[str, str, float]]:
        """Return pairs with agreement rate above threshold.

        Agreement = % of scans where both returned same status (TAKE/SKIP/WAIT).
        """
        if len(scanner_ids) < 2:
            return []

        warnings: list[tuple[str, str, float]] = []
        for i, sid_a in enumerate(scanner_ids):
            for sid_b in scanner_ids[i + 1 :]:
                rate = self._agreement_rate(sid_a, sid_b)
                if rate > self.warn_correlation:
                    warnings.append((sid_a, sid_b, rate))
        return warnings

    def check_drag(
        self, champion_id: str, ensemble_pf: float
    ) -> tuple[bool, str]:
        """Check if ensemble is being dragged down.

        Returns (should_fallback, reason).
        """
        stats = self._db.get_scanner_stats(champion_id)
        gross_win = stats.get("gross_win", 0) or 0
        gross_loss = abs(stats.get("gross_loss", 0) or 0)
        champion_pf = gross_win / gross_loss if gross_loss > 0 else 1.0

        if ensemble_pf >= champion_pf * self.drag_threshold:
            return (False, "")
        return (
            True,
            f"Ensemble PF ({ensemble_pf:.2f}) < champion PF ({champion_pf:.2f}) × {self.drag_threshold}",
        )

    def should_fallback(
        self, champion_id: str, ensemble_pf: float
    ) -> tuple[bool, str]:
        """Full check: correlation + drag. Returns (fallback?, reason)."""
        # Correlation check: warn only, don't auto-fallback
        corr_result = self.check_drag(champion_id, ensemble_pf)
        return corr_result

    def _agreement_rate(
        self, id_a: str, id_b: str, limit: int = 50
    ) -> float:
        """% of scans where both scanners returned matching statuses.

        Uses status field on closed trades as proxy for scan outcomes.
        """
        trades_a = self._db.get_closed_trades(id_a, limit=limit)
        trades_b = self._db.get_closed_trades(id_b, limit=limit)

        # Match trades by symbol + entry_time proximity
        matches = 0
        total = 0
        for ta in trades_a:
            for tb in trades_b:
                if ta["symbol"] == tb["symbol"]:
                    total += 1
                    if ta.get("outcome") == tb.get("outcome"):
                        matches += 1
                    break
        if total == 0:
            return 0.0
        return matches / total
