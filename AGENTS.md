<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# model-trader

## Purpose

A framework for turning a trader's recorded thinking (YouTube transcripts, articles, tweets) into an
executable screener and paper-trading bot. The pipeline is: content → strategy doc → scanner (gates) →
paper trader. This repo is the harness; each `traders/<name>/` project is a specific strategy built on it.

## Key Files

| File | Description |
|------|-------------|
| `pyproject.toml` | Project metadata, dependencies, optional extras (`pipeline`, `live`, `dev`, `all`); `src` package layout; pytest config (`testpaths=tests`, `pythonpath=src`) |
| `uv.lock` | Locked dependency versions for `uv` |
| `README.md` | Quickstart: scaffold → fetch transcripts → extract strategy → implement gates → backtest → run live |
| `.python-version` | Pinned Python version (3.12+) |
| `.gitignore` | Excludes `traders/*/trades.json`, `traders/*/ensemble.db`, `traders/*/transcripts/`, build artifacts |
| `LICENSE` | MIT |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | Installable Python packages: `model_trader` (the framework) and `pipeline` (one-shot CLIs) (see `src/AGENTS.md`) |
| `docs/` | Manual — read `docs/pipeline.md` first (see `docs/AGENTS.md`) |
| `tests/` | Unit tests for detectors (see `tests/AGENTS.md`) |
| `traders/` | Gitignored. Per-trader strategy projects scaffolded from `pipeline/scaffold_trader.py` (see `traders/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Source lives under `src/`; packages are discovered via `[tool.setuptools.packages.find] where = ["src"]`. When adding a new top-level package, ensure it's covered by that discovery (or add an explicit `pipeline*`/`model_trader*` include).
- Run CLIs and scripts with `uv run python -m ...` so the `src` layout resolves correctly.
- `traders/` is gitignored — trader projects (scanners, configs, journals) are local working copies, not shipped framework code. Don't assume a given `traders/<name>/` exists on a fresh checkout.
- The "agent layer" (`docs/agent-layer.md`) is deprecated and replaced by the ensemble voting engine in `model_trader/ensemble/`. Don't resurrect Claude-API-based scoring.

### Testing Requirements
- `uv run pytest` from repo root (testpaths = `tests/`, `pythonpath` includes `src/`).
- Detector changes need a corresponding test in `tests/test_<detector>.py`.

### Common Patterns
- Dataclasses for data shapes (`Candle` as TypedDict, `SetupResult`, `Trade`).
- ABC-based extension points: `DataAdapter` (data sources), `ScannerBase` (strategies), `Detector` (pattern detectors).
- Gates are ordered pass/fail checks; the last gate sets `entry`/`stop`/`target`/`direction` and flips status to `TAKE`.

## Dependencies

### External
- `requests`, `pyyaml` — always required
- `pytest` — dev extra
- `yt-dlp` — pipeline extra (transcript fetching)
- `hyperliquid-python-sdk` — live extra (exchange data/execution)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
