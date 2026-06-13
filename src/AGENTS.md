<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# src

## Purpose

Python source root (`[tool.setuptools.packages.find] where = ["src"]`). Contains the two installable
packages: the `model_trader` runtime framework and the `pipeline` one-shot CLI scripts used to bootstrap
new trader projects.

## Key Files

None — this directory only contains package directories.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `model_trader/` | The framework: data adapters, detectors, gates, paper trader, monitor, backtest runner, ensemble engine, executor (see `model_trader/AGENTS.md`) |
| `pipeline/` | One-shot CLIs: fetch transcripts, extract strategy context, scaffold a new trader project (see `pipeline/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Both `model_trader` and `pipeline` are importable as top-level packages once installed (`uv sync` / editable install) — imports are `from model_trader...` and `from pipeline...` or `python -m pipeline.scripts.<script>`.
- New packages added here must be discoverable by setuptools (see root `pyproject.toml`); a package without an `__init__.py` or not matching the configured patterns won't be installed.

### Testing Requirements
- `pythonpath = ["src"]` is set in `pyproject.toml`, so tests import directly from these packages without an install step.

### Common Patterns
- Each subpackage has its own `__init__.py` re-exporting its public API (see `model_trader/__init__.py` for the framework's full surface).

## Dependencies

### Internal
- `pipeline` generates projects that depend on `model_trader` at runtime.

### External
- See root `AGENTS.md` / `pyproject.toml`.

<!-- MANUAL: -->
