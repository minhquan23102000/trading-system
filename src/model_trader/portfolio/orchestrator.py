"""Portfolio orchestrator: runs multiple traders, sizes by composite, applies caps."""

from __future__ import annotations

from ..gates import ScannerBase, SetupResult, SetupStatus
from .sizing import (
    composite_from_journal,
    compute_weights,
    resolve_same_symbol,
    apply_correlation_cap,
    apply_aggregate_cap,
    daily_dd_breached,
)


class PortfolioOrchestrator:
    """Run N independent traders on their own symbols, size trades by composite score.

    Each scan cycle:
    1. Check daily drawdown stop.
    2. Run each scanner, collect TAKE setups, tag extras["trader_id"].
    3. Compute composite score per trader from the shared journal.
    4. Assign risk_pct via composite-weighted sizing.
    5. Filter already-open symbols.
    6. Resolve same-symbol conflicts (higher composite wins; opposite dirs -> drop both).
    7. Apply correlation-group cap.
    8. Apply aggregate open-risk cap.

    Args:
        scanners: trader_id -> ScannerBase instance. trader_id is used as the key
            in extras["trader_id"] and for journal lookup.
        trader: PaperTrader or HyperliquidExecutor (same interface).
        starting_balance: Account size at start; used for daily DD calculation.
        window_days: Rolling window for composite computation.
        min_trades: Closed trades required before a trader graduates from bootstrap.
        base_risk_pct: Base risk % per trade (1.0 = 1% of balance).
        min_risk_pct: Floor for per-trade risk after composite tilt.
        max_risk_pct: Ceiling for per-trade risk after composite tilt.
        max_portfolio_risk_pct: Max total open risk as % of balance.
        daily_dd_pct: Block new entries when today's realized loss exceeds this %.
        group_caps: Max concurrent positions per correlation group.
            Defaults to CRYPTO=2, METALS=1, INDEX=1.
    """

    def __init__(
        self,
        scanners: dict[str, ScannerBase],
        trader,
        starting_balance: float = 100_000.0,
        window_days: int = 90,
        min_trades: int = 10,
        base_risk_pct: float = 1.0,
        min_risk_pct: float = 0.25,
        max_risk_pct: float = 2.0,
        max_portfolio_risk_pct: float = 3.0,
        daily_dd_pct: float = 3.0,
        group_caps: dict[str, int] | None = None,
        seeds: dict[str, dict] | None = None,
    ):
        self.scanners = scanners
        self.trader = trader
        self.starting_balance = starting_balance
        self.window_days = window_days
        self.min_trades = min_trades
        self.base_risk_pct = base_risk_pct
        self.min_risk_pct = min_risk_pct
        self.max_risk_pct = max_risk_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.daily_dd_pct = daily_dd_pct
        self.group_caps = group_caps or {"CRYPTO": 2, "METALS": 1, "INDEX": 1}
        # seeds: {"trader_id": {"pf": float, "n": int}} — backtest priors for cold-start
        self.seeds: dict[str, dict] = seeds or {}
        self.last_results: list[SetupResult] = []

    def scan_cycle(self) -> list[SetupResult]:
        """Run all scanners and return approved TAKE decisions.

        Updates self.last_results with all scanner outputs (for dashboard).
        Returns only the filtered TAKEs ready for execution.
        """
        all_trades = self.trader.get_all_trades()
        open_trades = self.trader.get_open_trades()
        balance = self.trader.get_balance()

        # Daily DD stop: block new entries
        if daily_dd_breached(all_trades, self.starting_balance, self.daily_dd_pct):
            self.last_results = []
            return []

        # Run all scanners
        all_results: list[SetupResult] = []
        takes: list[SetupResult] = []
        for trader_id, scanner in self.scanners.items():
            try:
                results = scanner.scan_all()
            except Exception as e:  # noqa: BLE001
                print(f"  [{trader_id}] scan error: {e}", flush=True)
                continue
            all_results.extend(results)
            for r in results:
                if r.status == SetupStatus.TAKE:
                    r.extras.setdefault("trader_id", trader_id)
                    takes.append(r)

        self.last_results = all_results

        if not takes:
            return []

        # Composite scores + risk weights
        composites = {
            tid: composite_from_journal(
                all_trades, tid, self.window_days, self.min_trades,
                seed_pf=self.seeds.get(tid, {}).get("pf", 0.0),
                seed_n=self.seeds.get(tid, {}).get("n", 0),
            )
            for tid in self.scanners
        }
        weights = compute_weights(
            composites,
            base_pct=self.base_risk_pct,
            min_pct=self.min_risk_pct,
            max_pct=self.max_risk_pct,
            min_trades=self.min_trades,
        )
        for r in takes:
            tid = r.extras.get("trader_id", "")
            r.extras["risk_pct"] = weights.get(tid, self.base_risk_pct)

        # Already-open symbols get no new entry
        open_syms = {t["symbol"] for t in open_trades}
        takes = [r for r in takes if r.symbol not in open_syms]

        # Conflict resolution + caps
        takes = resolve_same_symbol(takes, composites)
        takes = apply_correlation_cap(takes, open_trades, self.group_caps)
        takes = apply_aggregate_cap(
            takes, open_trades, balance,
            self.max_portfolio_risk_pct, self.min_risk_pct,
        )

        return takes
