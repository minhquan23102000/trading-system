<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# ensemble

## Purpose

Champion-challenger weighted-voting engine that replaces the removed agent layer with deterministic, auditable trade decisions. Runs multiple scanner implementations in parallel with different detector weights, collects votes, auto-promotes high-performing challengers, and guards against ensemble degradation. All trades tracked in SQLite with per-scanner composite scoring.

## Key Files

| File | Description |
|------|-------------|
| `config.py` | `ScannerDef` (id, type, weight, strategy_module, params), `EnsembleConfig` (threshold, promotion settings, db_path, scanner list), `load_ensemble_config()` YAML parser |
| `engine.py` | `EnsembleEngine` — main voting loop, weighted vote collection, champion/challenger promotion, tie-breaking |
| `scoring.py` | `ScoreEngine` — composite scoring formula (profit_factor × ln(1 + trade_count) × stability_bonus), per-scanner ranking |
| `db.py` | `EnsembleDB` — SQLite trade table (scanner_id, symbol, entry/exit, pnl, outcome), open/closed queries, stats aggregation |
| `degradation.py` | `DegradationDetector` — correlation checks (>85% agreement = not independent), champion-drag detection (ensemble PF < champion PF × 0.9) |
| `__init__.py` | Public API — exports all five classes and the config parser |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **Scanners are complete strategies**: Each `ScannerDef` points to a full scanner module (e.g. `"scanner"`, `"scanner_supply_demand"`) that takes config + data adapter + **params and returns `SetupResult` lists. Not detectors, not gates—full trading strategies with independent gate logic.
- **Config → YAML schema**: `ensemble:` section in `config.yaml` defines threshold, db_path, promotion window, and a list of scanner definitions. See `docs/ensemble.md` for the full schema and examples.
- **Voting is deterministic**: TAKE votes are weighted by scanner weight, grouped by direction, checked against threshold. No randomness, no learned weights—pure weighted majority.
- **Promotion is gated**: Challengers only promoted after ≥10 trades (configurable), and max 1 promotion per 30-day window (configurable) to prevent flapping.
- **Degradation checks are automatic**: On every trade close, check correlation (are two scanners independent?) and champion drag (is ensemble losing money vs champion?). Can trigger fallback to champion-only.
- **SQLite is the single source of truth**: All scores, stats, and promotion decisions derive from the `trades` table. No in-memory state that survives a restart.
- **The engine holds scanner instances**: `EnsembleEngine.__init__(config, db, scanners)` takes a list of scanner objects. The monitor calls `engine.scan_all()`, which runs all active scanners and collects votes.

### Testing Requirements

- Tests live in `tests/test_ensemble.py` (if it exists); import directly from `model_trader.ensemble`.
- Unit test the voting logic: TAKE vote collection, weighted vote, threshold check, tie-breaking (champion breaks ties).
- Unit test promotion: challenger promoted when composite > champion composite AND trade_count ≥ min_trades, within promotion window limits.
- Unit test degradation: correlation calculated correctly, champion drag detected when ensemble PF < champion PF × threshold.
- Unit test scoring: composite = profit_factor × ln(1 + count) × stability, stability bonus applies when PF > 1.2 in current AND prior window.
- Do NOT mock the database; use an in-memory SQLite (`:memory:`) for isolation.

### Common Patterns

- **Dataclass configs**: `ScannerDef` and `EnsembleConfig` are dataclasses with defaults; `EnsembleConfig.get_champion()` and `active_scanners` are convenience properties.
- **Weighted voting**: `_collect_votes()` filters for TAKE status and scanner_id, tags each vote with scanner weight. `_weighted_vote()` groups by direction, picks highest-weight direction, applies threshold + tie-breaking.
- **Composite scoring**: `ScoreEngine.compute(scanner_id)` queries DB stats over a 30-day window, applies the formula, returns dict with profit_factor, trade_count, stability_bonus, composite.
- **SQLite schema**: Single `trades` table with scanner_id index + entry_time index; raw sqlite3 with WAL mode for zero-copy reads and robust writes.
- **Exception handling in scan_all()**: If any scanner raises, skip that result and continue—don't crash the ensemble.

## Dependencies

### Internal
- `gates` — `SetupResult` and `SetupStatus` (TAKE/SKIP/WAIT/NO_SETUP) types that every scanner returns
- `degradation`, `scoring`, `db`, `config` — sister modules within ensemble

### External
- `sqlite3` (stdlib) — WAL mode, raw parameterized queries, no ORM
- `dataclasses` (stdlib) — config dataclasses
- `pathlib` (stdlib) — database path handling

<!-- MANUAL: -->
