<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# traders

## Purpose

Gitignored. Per-trader strategy projects, each scaffolded by `pipeline/scaffold_trader.py` from a
trader's transcripts and implemented as a `Scanner(ScannerBase)` with its own gate pipeline, config,
backtest entry point, and live monitor entry point. Not shipped as part of the framework — these are
working/example projects local to this checkout.

## Key Files

None at this level — each `traders/<name>/` is a self-contained project.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `znasdaq/` | Gold (XAUUSD)/NASDAQ scanner: SMT divergence + FVG entry + failure-swing draws on liquidity (see `znasdaq/AGENTS.md`) |
| `mulham/` | HTF key-level + LTF confirmation 10-gate scanner, backtested across BTC/ETH/SOL/AVAX (see `mulham/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Each `<name>/` project follows the same shape: `scanner.py` (gates), `config.yaml` (symbols/timeframes/risk), `main.py` (live monitor entry), `backtest.py` (historical runner entry), `strategy.md` (extracted strategy doc), `philosophy_draft.md` (trader voice reference), `README.md` (profile/results).
- `trades.json`, `ensemble.db`, `transcripts/`, and `raw/` under each project are gitignored — don't expect them to exist on a fresh clone, and don't add framework code here that other projects need (put it in `src/model_trader/`).
- New trader projects are created via `uv run python -m pipeline.scripts.scaffold_trader <name>`, which refuses to overwrite an existing directory.

### Testing Requirements
- `cd traders/<name> && uv run python backtest.py` — validates `evaluate_at()` against historical data before running live.

### Common Patterns
- `Scanner` implements both `evaluate(symbol)` (live, calls the data adapter) and `evaluate_at(symbol, hist, corr_hist, ts)` (backtest, reads from passed-in history) with mirrored gate logic.
- Gates ordered by selectivity; reason strings populate `gates_passed`/`SetupResult.reason` for the live dashboard and journal.

## Dependencies

### Internal
- Imports from `model_trader` (detectors, `ScannerBase`, `SetupResult`/`SetupStatus`, `PaperTrader`, `run_monitor`, ensemble engine).

### External
- Per-project `config.yaml` may reference `model_trader.ensemble` scanner modules.

<!-- MANUAL: -->
