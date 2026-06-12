"""Ensemble voting engine — weighted vote, champion promotion.

The core decision loop:
1. All active scanners produce SetupResults
2. TAKE votes are collected, weighted by scanner weight
3. If total weight ≥ threshold → execute (use champion's entry/stop/target)
4. On trade close → update DB, check promotion, check degradation
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from ..gates import SetupResult, SetupStatus
from .config import EnsembleConfig, ScannerDef
from .db import EnsembleDB
from .degradation import DegradationDetector
from .scoring import ScoreEngine


@dataclass
class Vote:
    scanner_id: str
    direction: str
    weight: float
    setup: SetupResult | None = None


class EnsembleEngine:
    """Collects scanner votes → weighted decision → execute + track.

    Holds scanner instances internally. The monitor calls `scan_all()`
    to get filtered decisions; the engine runs all scanners, collects
    votes, and applies weighted voting.
    """

    def __init__(
        self,
        config: EnsembleConfig,
        db: EnsembleDB,
        scanners: list | None = None,
    ):
        self.config = config
        self._db = db
        self._score = ScoreEngine(db)
        self._degrade = DegradationDetector(db)
        self._scanners: list = scanners or []
        self._recent_promotions: list[float] = []  # timestamps
        self._ensure_champion()

    # ── main entry point ──────────────────────────────────

    def scan_all(self) -> list[SetupResult]:
        """Run all active scanners, collect votes, return TAKE decisions.

        This is the main entry point for the monitor loop.
        Returns: list of SetupResult to execute (empty if vote fails).
        """
        if not self._scanners:
            return []

        all_results: list[SetupResult] = []
        for s in self._scanners:
            try:
                results = s.scan_all()
                # Tag each result with scanner_id for vote collection
                scanner_id = getattr(s, "_scanner_id", None) or type(s).__name__
                for r in results:
                    r.extras["scanner_id"] = scanner_id
                all_results.extend(results)
            except Exception:
                continue

        return self.evaluate_all(all_results)

    def evaluate_all(
        self, setups: list[SetupResult]
    ) -> list[SetupResult]:
        """Run N scanner results through weighted vote → return TAKE decisions.

        setups: one SetupResult per active scanner per scan cycle.
        Returns: list of SetupResult to execute (empty if vote fails).
        """
        if not setups:
            return []

        # Collect TAKE votes
        votes = self._collect_votes(setups)
        if not votes:
            return []

        # Group by symbol (all setups are for same symbol in one scan)
        passed, total_weight, reason = self._weighted_vote(votes)
        if not passed:
            return []

        # Use champion's setup for entry/stop/target details
        champion = self.config.get_champion()
        if champion is None:
            return []

        decision = self._build_decision(setups[0].symbol, votes)
        return [decision]

    # ── voting logic ──────────────────────────────────────

    def _collect_votes(self, setups: list[SetupResult]) -> list[Vote]:
        """Collect TAKE votes with configured weights."""
        votes: list[Vote] = []
        scanner_map = {s.id: s for s in self.config.active_scanners}

        for r in setups:
            if r.status != SetupStatus.TAKE:
                continue
            scanner_id = getattr(r, "scanner_id", None) or getattr(
                r, "extras", {}
            ).get("scanner_id")
            if scanner_id and scanner_id in scanner_map:
                weight = scanner_map[scanner_id].weight
                votes.append(
                    Vote(
                        scanner_id=scanner_id,
                        direction=r.direction or "long",
                        weight=weight,
                        setup=r,
                    )
                )

        return votes

    def _weighted_vote(self, votes: list[Vote]) -> tuple[bool, float, str]:
        """Group by direction, pick majority, check threshold."""
        by_dir: dict[str, list[Vote]] = {}
        for v in votes:
            by_dir.setdefault(v.direction, []).append(v)

        if not by_dir:
            return (False, 0.0, "No TAKE votes")

        # Pick direction with highest total weight
        dir_weights = {
            d: sum(v.weight for v in vl) for d, vl in by_dir.items()
        }
        best_dir = max(dir_weights, key=lambda d: dir_weights[d])
        total_weight = dir_weights[best_dir]
        rival_dirs = {d: w for d, w in dir_weights.items() if d != best_dir}
        best_rival = max(rival_dirs.values()) if rival_dirs else 0

        # Tie-breaking
        if total_weight == best_rival:
            champion = self.config.get_champion()
            if champion and champion.id in self.config.active_scanner_ids:
                # Champion breaks tie
                champ_votes = [v for v in votes if v.scanner_id == champion.id]
                if champ_votes:
                    champ_dir = max(
                        set(v.direction for v in champ_votes),
                        key=lambda d: sum(
                            1 for v in champ_votes if v.direction == d
                        ),
                    )
                    if champ_dir == best_dir:
                        pass  # champion confirms
                    else:
                        return (
                            False,
                            total_weight,
                            "Direction tie — champion disagrees, SKIP",
                        )
            else:
                # No champion: check voter count
                voter_cnt = {d: len(vl) for d, vl in by_dir.items()}
                best_cnt = max(voter_cnt.values())
                cnt_tied = sum(1 for c in voter_cnt.values() if c == best_cnt)
                if cnt_tied > 1:
                    return (
                        False,
                        total_weight,
                        "Direction tie — same weight + voter count, SKIP",
                    )

        if total_weight >= self.config.vote_threshold:
            return (
                True,
                total_weight,
                f"Vote passed: {total_weight:.2f} ≥ {self.config.vote_threshold}",
            )
        return (
            False,
            total_weight,
            f"Vote failed: {total_weight:.2f} < {self.config.vote_threshold}",
        )

    def _build_decision(
        self, symbol: str, votes: list[Vote]
    ) -> SetupResult:
        """Merge entry/stop/target from champion's setup."""
        champion = self.config.get_champion()
        champ_vote = next(
            (v for v in votes if v.scanner_id == champion.id), None
        ) if champion else None
        # Fallback to first vote if champion didn't vote
        source = champ_vote or votes[0]

        # Use champion's setup details if available
        best_dir = max(
            set(v.direction for v in votes),
            key=lambda d: sum(1 for v in votes if v.direction == d),
        )
        result = SetupResult(
            symbol=symbol,
            status=SetupStatus.TAKE,
            direction=best_dir,
            reason=f"Ensemble vote ({len(votes)} scanners)",
        )
        if source.setup:
            result.entry = source.setup.entry
            result.stop = source.setup.stop
            result.target = source.setup.target
            result.extras = {
                **source.setup.extras,
                "ensemble_scanner_id": source.scanner_id,
            }
        return result

    # ── lifecycle callbacks ────────────────────────────────

    def on_trade_opened(self, trade: dict[str, Any]) -> None:
        """Record an opened trade in the DB."""
        self._db.insert_trade(trade)

    def on_trade_closed(self, trade: dict[str, Any]) -> None:
        """Update DB, check promotion, check degradation."""
        trade_id = trade.get("id") or trade.get("trade_id")
        if trade_id:
            self._db.update_trade(trade_id, **trade)

        # Check promotion after every closed trade
        self._check_promotions()

        # Check degradation
        self._check_degradation()

    def on_scan_complete(self, setups: list[SetupResult]) -> None:
        """Log scan stats. Hook for future analytics."""
        pass

    # ── promotion ─────────────────────────────────────────

    def _ensure_champion(self) -> None:
        """Validate champion exists and is active. Promote if needed."""
        champion = self.config.get_champion()
        if champion is None:
            raise EnsembleError("No champion configured — at least one scanner must be champion")
        if not champion.active:
            # Promote highest-weight active challenger
            challengers = self.config.active_challengers()
            if not challengers:
                raise EnsembleError("Champion inactive and no active challengers to promote")
            best = max(challengers, key=lambda s: s.weight)
            best.type = "champion"
            best.weight = 0.5  # new champion gets standard champion weight

    def _check_promotions(self) -> None:
        """Check if any challenger should be promoted."""
        # Min trades filter — only check scanners with enough trades
        for challenger in self.config.active_challengers():
            stats = self._db.get_scanner_stats(challenger.id)
            if stats["trade_count"] < self.config.promotion_min_trades:
                continue

        # Noise filter — max promotions per window
        now = time.time()
        window = self.config.promotion_window_days * 86400
        self._recent_promotions = [
            t for t in self._recent_promotions if now - t < window
        ]
        if len(self._recent_promotions) >= self.config.max_promotions_per_window:
            return

        # Score comparison
        champion = self.config.get_champion()
        if champion is None:
            return
        active_ids = [s.id for s in self.config.active_scanners]
        rankings = self._score.rank_all(active_ids)

        champion_score = next(
            (r for r in rankings if r["scanner_id"] == champion.id), None
        )
        if champion_score is None:
            return

        for challenger in self.config.active_challengers():
            challenger_score = next(
                (r for r in rankings if r["scanner_id"] == challenger.id),
                None,
            )
            if challenger_score is None:
                continue
            if challenger_score["trade_count"] < self.config.promotion_min_trades:
                continue
            if challenger_score["composite"] > champion_score["composite"]:
                self._promote(challenger)

    def _promote(self, challenger: ScannerDef) -> None:
        """Promote a challenger to champion. Demote old champion."""
        old_champion = self.config.get_champion()
        if old_champion:
            old_champion.type = "challenger"
            old_champion.weight = 0.25
        challenger.type = "champion"
        challenger.weight = 0.5
        self._recent_promotions.append(time.time())

    # ── degradation ────────────────────────────────────────

    def _check_degradation(self) -> None:
        """Run correlation and drag checks. Log warnings, auto-fallback."""
        champion = self.config.get_champion()
        if champion is None:
            return

        # Compute ensemble PF from DB
        ensemble_pf = self._compute_ensemble_pf()

        should_fallback, reason = self._degrade.should_fallback(
            champion.id, ensemble_pf
        )
        if should_fallback:
            # Fallback: champion-only mode (just log for now, config tracks it)
            self.config.fallback_active = True

        # Correlation warnings
        active_ids = [s.id for s in self.config.active_scanners]
        warnings = self._degrade.check_correlation(active_ids)
        for a, b, rate in warnings:
            # Log correlation warning (just print for now)
            pass

    def _compute_ensemble_pf(self) -> float:
        """Compute aggregate profit factor across all scanners in recent window."""
        stats = self._db.get_scanner_stats(
            "_ensemble_", window_days=self._score.window_days
        )
        gross_win = stats.get("gross_win", 0) or 0
        gross_loss = abs(stats.get("gross_loss", 0) or 0)
        if gross_loss == 0:
            return gross_win if gross_win > 0 else 1.0
        return gross_win / gross_loss


class EnsembleError(Exception):
    """Configuration or runtime error in the ensemble system."""
    pass
