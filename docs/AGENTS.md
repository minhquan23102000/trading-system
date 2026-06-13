<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# docs

## Purpose

The manual. Explains the end-to-end pipeline, runtime architecture, and the hardest part of the
process — translating a trader's prose strategy into pass/fail gates.

## Key Files

| File | Description |
|------|-------------|
| `pipeline.md` | **Start here.** The five stages: ingest → extract → scaffold → implement → validate |
| `architecture.md` | How the runtime pieces fit together (DataAdapter → Detectors → Scanner → Filters/Ensemble → PaperTrader → monitor loop), the `Candle`/`SetupResult`/`Trade` data model, and what the framework deliberately does not do |
| `designing-gates.md` | How to turn a prose strategy into an ordered chain of pass/fail gates — one responsibility per gate, ordered by selectivity, last gate sets entry/stop/target and flips status to `TAKE` |
| `backtest.md` | How to implement `evaluate_at()` and validate gates against history before going live |
| `ensemble.md` | Multi-scanner weighted voting: champion/challenger roles, auto-promotion, SQLite-backed scoring, `config.yaml` schema |
| `adding-data-sources.md` | How to write a new `DataAdapter` subclass to support exchanges/brokers beyond Hyperliquid |
| `agent-layer.md` | **Deprecated** — the old Claude-API discretion layer, replaced by `model_trader/ensemble/`. Historical reference only |

## Subdirectories

None.

## For AI Agents

### Working In This Directory
- Read `pipeline.md` then `architecture.md` before making framework-level changes — they define the contracts (`SetupResult`, `SetupStatus`, gate ordering) that all scanners depend on.
- If you change a contract described here (e.g. `SetupResult` fields, the scan-and-execute loop order), update the corresponding doc in the same change.
- Do not extend `agent-layer.md` or reintroduce a Claude-API scoring path — that's superseded by `ensemble.md`.

### Testing Requirements
- N/A (documentation only).

### Common Patterns
- Each doc favors short prose + code/diagram blocks over exhaustive API reference; keep new docs in that style.

## Dependencies

### Internal
- Describes `src/model_trader/*` and `src/pipeline/*` behavior; keep in sync with those packages.

### External
- None.

<!-- MANUAL: -->
