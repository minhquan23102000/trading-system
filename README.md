# model-trader

Turn a trader's content into an executable screener and paper trader.

A framework for building algorithmic trading bots from the recorded thinking of
real traders. You feed in the trader's transcripts (YouTube videos, articles,
tweets), distill their strategy into a set of pass/fail gates, and run the
result as a live screener that paper trades on Hyperliquid.

```
content  ->  strategy doc  ->  scanner (gates)  ->  paper trader
```

## Why this exists

Most trading is judgment, not rules. But the *structure* of a trader's judgment — which patterns they look for, what invalidates a setup, when they sit on their hands — can usually be expressed as a short pipeline of pass/fail checks. This repo is a scaffold for doing that translation: from someone's recorded thinking into code that takes the same setups they would, on the same symbols, with the same risk model.

It is not a strategy. It is the harness around one.

## What's in the box

- **`model_trader/`** — the framework
  - `data/` — `DataAdapter` ABC + `HyperliquidAdapter` (works with no API key)
  - `detectors/` — reusable pattern detectors (FVG, swings, CISD, SMT, displacement, failure swings)
  - `gates/` — `ScannerBase` and the `SetupResult` / `SetupStatus` types
  - `trading/` — JSON-journaled paper trader and live executors (e.g. Hyperliquid) sharing position-sizing/PnL math, plus duplicate and invalidated-level filters and metrics
  - `portfolio/` — multi-scanner orchestration, position sizing, capital allocation
  - `monitor/` — live monitor loop (scan → filter → execute → dashboard)
  - `backtest/` — historical runner that walks a scanner through past candles
  - `ensemble/` — champion-challenger weighted voting engine

- **`pipeline/`** — one-shot CLIs you run before going live
  - `fetch_youtube_transcripts.py` — pull captions from YouTube videos
  - `extract_strategy.py` — aggregate transcripts into extraction context for AI to read
  - `scaffold_trader.py` — generate a new `traders/<name>/` project from templates

- **`docs/`** — the manual (start with [docs/pipeline.md](docs/pipeline.md))

- **`traders/`** — included examples: `mulham`, `znasdaq`, `tradingnotes`. Your trader projects live here.

## Ensemble mode

Run multiple complete trading strategies with weighted voting. Each scanner is
a full strategy — same module with different params, or entirely different approaches.
Configured in YAML — no code changes needed.

```yaml
# In config.yaml:
ensemble:
  threshold: 0.5               # min total weight to execute
  promotion_min_trades: 10     # before challenger can become champion
  scanners:
    - id: "default"
      type: "champion"
      weight: 0.5
      strategy_module: "scanner"   # full strategy module
      params: {}
    - id: "loose"
      type: "challenger"
      weight: 0.25
      strategy_module: "scanner"   # same strategy, looser gates
      params: {"fvg_tolerance": 2.0}
```

Champion sets entry/stop/target. Challengers vote. Auto-promotion based on
profit factor tracked in SQLite.

## Quickstart

```bash
git clone <this-repo> model-trader
cd model-trader
uv sync

# 1. Scaffold a new trader project
uv run python -m pipeline.scripts.scaffold_trader my_trader

# 2. Pull transcripts from a few of their videos
uv run python -m pipeline.scripts.fetch_youtube_transcripts traders/my_trader/transcripts VIDEO_ID_1 VIDEO_ID_2

# 3. Prepare transcripts for AI extraction (no API key needed)
uv run python -m pipeline.scripts.extract_strategy traders/my_trader/transcripts traders/my_trader

# 4. Ask your AI assistant to extract the strategy:
#    "Read traders/my_trader/_extraction_context.md and follow pipeline/SKILL.md"
#    The AI produces strategy.md directly in chat.

# 5. Backtest and iterate
cd traders/my_trader
uv run python backtest.py

# 6. Run the live monitor
uv run python main.py
```

Paper trading is on by default. No real money is at risk unless you write code
to put it there.

## Reading order

If you're new to this repo, follow the docs in this order:

1. [`docs/pipeline.md`](docs/pipeline.md) — the end-to-end flow
2. [`docs/architecture.md`](docs/architecture.md) — how the pieces fit together
3. [`docs/designing-gates.md`](docs/designing-gates.md) — the hard part: turning prose into pass/fail checks
4. [`docs/backtest.md`](docs/backtest.md) — how to validate your gates against history
5. [`docs/ensemble.md`](docs/ensemble.md) — multi-strategy voting and promotion
6. [`docs/portfolio.md`](docs/portfolio.md) — capital allocation, position sizing, multi-scanner orchestration
7. [`docs/adding-data-sources.md`](docs/adding-data-sources.md) — swapping Hyperliquid for something else

## Requirements

- Python 3.12+
- `requests`, `pyyaml` (always required)
- `yt-dlp` (pipeline extra — transcript fetching)
- `hyperliquid-python-sdk` (live extra — exchange execution + data)