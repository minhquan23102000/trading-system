<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# pipeline

## Purpose

One-shot CLI scripts for stages 1–3 of the trader bootstrapping pipeline. Convert a trader's recorded thinking (YouTube transcripts, articles, tweets) into a fresh trader project scaffold ready for gate implementation. These scripts are invoked once per new trader project and then discarded — they do not run during live trading or backtesting.

The five-stage pipeline is: (1) Ingest → (2) Extract → (3) Scaffold → (4) Implement → (5) Validate. This directory covers 1–3; stage 4 is manual gate implementation; stage 5 runs from `model_trader/`.

## Key Files

| File | Description |
|------|-------------|
| `fetch_youtube_transcripts.py` | Download auto-generated captions from YouTube videos (one `--video-id` per arg); strips VTT formatting, deduplicates timing-repeats, writes clean `.txt` per video. Requires `yt-dlp`. |
| `extract_strategy.py` | Aggregate all transcript `.txt` files in a directory into `_extraction_context.md` — a single file combining transcripts + extraction instructions for AI-assisted strategy doc generation. No API key needed. |
| `scaffold_trader.py` | Create `traders/<name>/` directory with boilerplate: `scanner.py` template, `config.yaml`, `main.py`, `backtest.py`, `philosophy.md` (voice template). Safe to re-run; refuses to overwrite existing `traders/<name>/`. |
| `__init__.py` | Empty marker. Pipeline is importable as `from pipeline ...` once installed. |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **Invocation:** These are runnable as modules with `python -m pipeline.<script>`. For example:
  - `python -m pipeline.fetch_youtube_transcripts traders/my_trader/transcripts VIDEO_ID1 VIDEO_ID2 VIDEO_ID3`
  - `python -m pipeline.extract_strategy traders/my_trader/transcripts traders/my_trader`
  - `python -m pipeline.scaffold_trader my_trader`
  - (Run with `uv run` in the repo root to ensure the `src` layout resolves: `uv run python -m pipeline.fetch_youtube_transcripts ...`)

- **Skill reference:** `extract_strategy.py` mentions `.omc/skills/trade-setup-scanner/SKILL.md` Phase 1 in its instructions, not a `pipeline/SKILL.md`. If you are working with the trader extraction workflow interactively in Claude, follow the trade-setup-scanner skill; this module generates only the `_extraction_context.md` file.

- **Dependency:** `fetch_youtube_transcripts.py` requires the `yt-dlp` optional extra. Install with `uv sync --extra pipeline` or `pip install yt-dlp`.

- **One-shot tools:** These scripts are not meant to be called repeatedly or in a loop. They are scaffolding helpers that run once per new trader project. After scaffolding, the trader works in `traders/<name>/` using `model_trader` framework APIs (scanner, config, gates, backtester).

- **Docs mismatch:** `docs/pipeline.md` references `python -m pipeline.scripts.*` in its examples, but the actual module paths are `python -m pipeline.*` (no `scripts` subpackage). The documentation examples need correction, but the actual invocation commands above are correct.

### Testing Requirements

- No unit tests for pipeline scripts. These are one-shot CLIs with side effects (file I/O). Verification is manual: check that scaffolded output files exist and are well-formed.
- The scaffolded `traders/<name>/` projects should import `model_trader` without error; verify with `python -c "from model_trader import ScannerBase; print(ScannerBase)"` in a fresh trader dir.

### Common Patterns

- All three scripts check `len(sys.argv)`, define a `main()` function, and run it under `if __name__ == "__main__"`.
- All three are runnable as modules because they have `if __name__ == "__main__": main()` blocks.
- `fetch_youtube_transcripts.py` calls `yt-dlp` via `subprocess.run()` to avoid a hard dependency; gracefully handles missing captions (returns `None`).
- `extract_strategy.py` and `scaffold_trader.py` are pure I/O: they read templates, interpolate variables, and write files. No external service calls.
- Paths are all `Path` objects (pathlib) for cross-platform compatibility.

## Dependencies

### Internal

- `model_trader` — the scaffolded `traders/<name>/` projects import from `model_trader.gates`, `model_trader.detectors`, `model_trader.backtest`, etc. This is a runtime dependency of the scaffolded projects, not of the pipeline scripts themselves.

### External

- `yt-dlp>=2024.1.0` — optional extra, required only for `fetch_youtube_transcripts.py`. Install with `uv sync --extra pipeline` or `pip install yt-dlp`.
- `pyyaml` — the scaffold templates include `config.yaml` (YAML files), but the scripts only write strings; no parsing needed. YAML handling is in scaffolded projects, not in pipeline itself.

<!-- MANUAL: -->
