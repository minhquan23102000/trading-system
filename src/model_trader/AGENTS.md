<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# model_trader

## Purpose

The runtime framework. Provides everything a trader project (`traders/<name>/`) imports: data adapters,
pattern detectors, the gate/scanner base classes, the paper trader, the live monitor loop, the backtest
runner, and the ensemble voting engine. See `docs/architecture.md` for the layered view and
`docs/pipeline.md` for the end-to-end workflow.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Public API surface — re-exports `DataAdapter`, `HyperliquidAdapter`, all detectors, `ScannerBase`/`SetupResult`/`SetupStatus`, `PaperTrader`, `run_monitor`, and the ensemble classes |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `data/` | `DataAdapter` ABC + `HyperliquidAdapter` — candle fetching (see `data/AGENTS.md`) |
| `detectors/` | Pure-function pattern detectors: FVG, swings, CISD, SMT, displacement, failure swings (see `detectors/AGENTS.md`) |
| `gates/` | `ScannerBase` and the `SetupResult`/`SetupStatus` types every scanner is built from (see `gates/AGENTS.md`) |
| `trading/` | JSON-journaled paper trader, shared sizing/PnL journal math, duplicate/invalidated-level filters, metrics, and live executors (see `trading/AGENTS.md`) |
| `monitor/` | Live monitor loop: scan → filter → execute → dashboard (see `monitor/AGENTS.md`) |
| `backtest/` | Historical runner that walks a scanner through past candles (see `backtest/AGENTS.md`) |
| `ensemble/` | Champion/challenger weighted-voting engine with SQLite-backed scoring (see `ensemble/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Each layer depends only on layers below it (data → detectors → gates/scanner → filters/ensemble → monitor/backtest). Don't introduce upward dependencies (e.g. a detector importing from `monitor`).
- Adding a new public symbol? Export it from `__init__.py` and add it to `__all__` — trader projects import via `from model_trader import ...`.
- This package is the stable framework; trader-specific logic (gates, scanners) lives in `traders/<name>/`, not here.

### Testing Requirements
- `uv run pytest` — detector tests live in `tests/test_<detector>.py` and import directly from `model_trader.detectors`.

### Common Patterns
- `Candle` is a TypedDict (plain dict at runtime) with `timestamp`/`open`/`high`/`low`/`close`/`volume`.
- Detectors are pure functions over candle lists — no state, no I/O.
- `SetupResult` / `SetupStatus` (`NO_SETUP`/`SKIP`/`WAIT`/`TAKE`) are the universal scanner output contract.

## Dependencies

### Internal
- All subdirectories listed above compose into this package's `__init__.py` surface.

### External
- `requests` (HTTP for data/executor adapters), `pyyaml` (config), `hyperliquid-python-sdk` (live extra).

<!-- MANUAL: -->
