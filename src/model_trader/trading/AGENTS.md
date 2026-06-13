<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# trading

## Purpose

Everything related to opening, sizing, and closing trades — paper and live —
lives here. `paper.py` simulates a trading account and persists the journal
to JSON so state survives restarts. `journal.py` holds the JSON
persistence, risk-based position sizing, and close/PnL math shared with live
executors in `live/`, plus the `Trader` structural protocol both `PaperTrader`
and `live.HyperliquidExecutor` satisfy. Two filters (`is_duplicate_setup`,
`is_invalidated_level`) prevent common failure modes: scanners that re-trigger
on the same bar producing duplicates, and re-entries after a stop loss at a
level that hasn't structurally invalidated. Metrics are computed on-demand
from the journal for dashboard and analysis.

## Key Files

| File | Description |
|------|-------------|
| `journal.py` | Shared primitives: `load_journal()`/`save_journal()` (JSON persistence), `size_with_leverage_cap()` (risk-based sizing with leverage cap), `apply_close()` (mutates a trade dict into its closed state — pnl, r_multiple, outcome, notes), and the `Trader` `Protocol` (structural contract: `execute`, `check_exits`, `get_open_trades`, `get_all_trades`, `get_balance`) |
| `paper.py` | `PaperTrader` class and `Trade` dataclass: opens trades via `execute(SetupResult)`, closes on TP/SL via `check_exits()`, stores account state (balance, open/closed trades) |
| `filters.py` | Two filter functions: `is_duplicate_setup()` (same entry/SL/TP within tolerance recently closed) and `is_invalidated_level()` (stop is near a blown level and price hasn't moved far enough away) |
| `metrics.py` | `calculate_metrics()` computes W/L count, win rate, avg R-multiple, profit factor, total PnL, max drawdown from closed trades |
| `__init__.py` | Exports `PaperTrader`, `Trade`, `Trader`, `is_duplicate_setup`, `is_invalidated_level`, `calculate_metrics`, and the `journal` helpers |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `live/` | Live order-execution adapters (e.g. `HyperliquidExecutor`) — see `live/AGENTS.md` |

## For AI Agents

### Working In This Directory

**The `Trader` protocol:**
- `journal.Trader` is a `typing.Protocol` capturing the surface both `PaperTrader` and `live.HyperliquidExecutor` already implement: `execute(setup) -> ... | None`, `check_exits() -> list[dict]`, `get_open_trades() -> list[dict]`, `get_all_trades() -> list[dict]`, `get_balance() -> float`.
- Both classes satisfy it structurally (duck typing) — no inheritance needed. `PortfolioOrchestrator(trader: Trader, ...)` and a trader's `main.py` can type against `Trader` and swap paper/live implementations without changing call sites.
- Do **not** force a common base class or unify `__init__` signatures / `execute()` return types — `PaperTrader` returns a `Trade` dataclass, `HyperliquidExecutor` returns a journal dict with exchange-only fields (`entry_oid`, `sl_oid`, `tp_oid`, `fill_time`). That divergence is intentional (see `live/AGENTS.md`).

**The PaperTrader and its journal:**
- `PaperTrader` wraps a JSON journal at `journal_path` (typically `traders/<name>/trades.json`) via `journal.load_journal()`/`journal.save_journal()`.
- Each trade is a dict with: `id`, `symbol`, `direction` ("long"/"short"), `entry_price`, `stop_loss`, `take_profit`,
  `position_size`, `risk_amount`, `rr_ratio`, `status` ("OPEN"/"CLOSED"), `entry_time` (ISO 8601),
  `exit_time` (ISO 8601 or None), `exit_price` (float or None), `pnl` (float or None), `r_multiple` (float or None),
  `outcome` ("WIN"/"LOSS"/"BE" or None), `notes` (e.g., "SL_HIT", "TP_HIT"), `extras` (dict of scanner-supplied fields).
- `PaperTrader.execute(setup: SetupResult)` opens a trade: validates setup status and prices, sizes via
  `journal.size_with_leverage_cap(balance, pct, entry, stop_dist, max_leverage)`, writes to journal. Returns `Trade | None`.
- `PaperTrader.check_exits()` fetches the latest 1m candle for each open trade, checks candle high/low against
  SL and TP. If SL hit, closes with "SL_HIT" via `journal.apply_close()`; if TP hit, closes with "TP_HIT". Computes PnL and R-multiple.
  Returns list of newly-closed trades.
- Balance calculation: `starting_balance + sum of realized PnL from CLOSED trades`. Compounds over time.

**The two filters:**
- `is_duplicate_setup(journal_path, symbol, entry, stop, target, lookback_minutes=15, tolerance_pct=0.02)`:
  Returns True if a trade with the same symbol and entry/stop/target (within `tolerance_pct` of each price)
  closed in the last `lookback_minutes`. Prevents oscillating back through a breaker level that just triggered.
  Used in `run_monitor` before `execute()`.
- `is_invalidated_level(journal_path, symbol, direction, stop, current_price, max_age_hours=6, tolerance_pct=0.2, required_distance_pct=0.5)`:
  Returns True if a trade with the same symbol and direction had a SL hit near the proposed stop (within `tolerance_pct`)
  in the last `max_age_hours` AND current price hasn't moved `required_distance_pct` in the trade's favor away from
  the blown level. For long: requires `current_price >= blown_level + required_distance`.
  For short: requires `current_price <= blown_level - required_distance`.
  Prevents cascading losses on the same blown structure.

**Position sizing (`journal.size_with_leverage_cap`):**
- Fixed-% risk: `risk = balance * (per_trade_pct / 100)`; `size = risk / stop_distance`.
- Leverage cap: `notional = size * entry` must not exceed `balance * max_leverage`. If it would, shrinks size (and `risk`) accordingly.
- Callers compute `rr_ratio = target_distance / stop_distance` themselves (not part of the shared helper, since `HyperliquidExecutor` needs it before rounding).

### Testing Requirements

Paper trader tests live in `tests/test_trader.py` (if any) or integration tests that exercise the monitor loop.
- Key invariants: journal persists across restarts, balance compounds only on realized trades,
  open trades don't affect balance, check_exits correctly detects high/low hits and prioritizes SL over TP,
  filters correctly reject duplicates and invalidated levels with the specified tolerances.
- `journal.size_with_leverage_cap()` and `journal.apply_close()` are shared with `live/hyperliquid.py` — a regression in either affects both paper and live sizing/PnL.

### Common Patterns

- Always validate `setup.status == SetupStatus.TAKE` and all price fields non-None before opening a trade.
- Use candle `high` and `low` for exit checks, not just `close`, so wicks are not missed.
- If both SL and TP hit in the same candle, SL takes priority (conservative).
- Filters look at `notes` field (set to exit reason) and `exit_time` field to decide recency.
- R-multiple is `pnl / (size * stop_distance)`, not the ratio; it measures PnL in units of risk.

## Dependencies

### Internal
- `..gates`: `SetupResult`, `SetupStatus` (status checks, extras pass-through).
- Data adapter (passed to `PaperTrader.__init__`): used to fetch 1m candles for exit checks.

### External
- `json`, `uuid`, `dataclasses`, `datetime`, `pathlib` (stdlib only).

<!-- MANUAL: -->
