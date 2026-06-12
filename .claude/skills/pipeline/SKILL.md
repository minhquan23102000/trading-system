---
name: trade-setup-scanner
description: Extract and implement trading strategies from trader transcripts in this repo (model-trader, uv-managed)
triggers:
  - extract strategy from this trader
  - scanner
  - transcript
  - strategy
  - gates
  - backtest
  - paper trader
  - ICT
---

# Trade Setup Scanner (model-trader)

Turn a trader's transcripts into an executable gate-based scanner + paper-trading
bot under `traders/<name>/`. The framework (`model_trader/`) provides detectors,
gate infrastructure, paper trading, ensemble voting, and a live monitor — your
job is to translate the trader's thinking into pass/fail gates and validate them
against history.

This is the ONLY skill for the extract → implement → backtest → iterate workflow.
There is no other authoritative source — the docs have stale bare-`python` commands.
Everything below is verified against the live `uv run` environment.

## Environment

**This project uses uv, not bare Python.** Every command must be prefixed:
```bash
uv sync                 # install deps
uv sync --extra all     # install + yt-dlp + hyperliquid-python-sdk

# Pipeline scripts (one-shot, before going live)
uv run python -m pipeline.scaffold_trader my_trader
uv run python -m pipeline.fetch_youtube_transcripts traders/my_trader/transcripts VID1 VID2
uv run python -m pipeline.extract_strategy traders/my_trader/transcripts traders/my_trader

# Trader project (runtime)
uv run python backtest.py
uv run python main.py
```

The bare `python` / `python -m` commands in `docs/pipeline.md` are stale — always use `uv run`.

`traders/` is gitignored. Trader projects and `trades.json` are local-only.

---

## Phase 1: Extract Strategy from Transcripts

The goal is to produce `strategy.md` — a structured document that captures what
the trader actually does, not what they say they do. Prefer what they DO over
what they SAY (if they claim to wait for CISD but every example entry is at an
FVG, note the discrepancy).

### Step 1.1: Read all transcripts

If transcripts don't exist yet, fetch them:
```bash
uv run python -m pipeline.fetch_youtube_transcripts traders/<name>/transcripts VIDEO_ID_1 VIDEO_ID_2 ...
```
Or drop `.txt` files into that directory manually.
- Total character count (10k-100k chars is useful; less = insufficient data)
- Any garbled auto-captions or wrong-language transcripts

### Step 1.2: Write `strategy.md`

Write to `traders/<name>/strategy.md`. Use this template:

```markdown
# [Trader Name] — Strategy Breakdown

## Core Identity
[Who they are, background, what gives them edge. 1 paragraph.]

## Ranked Priorities
[What they emphasize most → least. Direct quotes where possible.]

## The Setup(s)
### Setup: [Name]
- **Trigger:** [exact conditions]
- **Timeframes:** [HTF + LTF involved]
- **Entry:** [exact rule]
- **Stop:** [invalidation point]
- **Target:** [default + when to hold/exit early]
- **Does NOT apply when:** [explicit exclusions]

[Repeat for each distinct setup — usually 1-3]

## Key Concepts
[Every term they use that matters for implementation. Define each with
THEIR definition, not textbook. Examples: CISD, FVG, draw on liquidity,
failure swing, SMT, displacement.]

## Gates (Draft Pipeline)
Gate 1: [name] — [what to check]
  Pass: [condition]  |  Fail: [condition]
Gate 2: ...
...

## Anti-Patterns
[What they explicitly avoid. Direct quotes preferred.]

## Risk Management
[Position sizing, max risk, daily limits. Quoted if possible.]

## Voice & Vocabulary
[Characteristic phrases, how they talk about setups, what "clean" vs
"forced" sounds like in their words.]
```

Extraction rules:
- Quote directly when the trader says something characteristic
- Note contradictions — traders contradict themselves; flag them openly
- Don't invent gates the trader didn't actually use
- Be specific about timeframes — "HTF" alone is useless; is it 1h? 4h? daily?

### Step 1.3: Write `philosophy_draft.md`

Write to `traders/<name>/philosophy_draft.md`. A first-person document in the
trader's voice, 2,000-4,000 words. It serves as a reference for understanding
how they think — not a system prompt (the agent layer is gone).

Structure with these sections:
- **Who I am** — first person, their edge
- **Core philosophy** — 5-10 principles with quotes
- **The setup(s) I trade** — detailed, concrete
- **Entry mechanics** — exact sequence
- **Stop loss** — invalidation-based rule
- **Take profit** — default + exceptions
- **"Am I actually taking this?" checklist** — 5-10 questions in their voice
- **Anti-patterns** — what they DO NOT do
- **Psychology / mindset** — how they stay disciplined
- **My voice** — example phrases

Strip generic platitudes ("manage risk", "be patient"). Be specific about
what the trader actually does — vague philosophy won't help when implementing
gates.

---

## Phase 2: Scaffold the Trader Project

```bash
uv run python -m pipeline.scaffold_trader my_trader
```

Creates `traders/<name>/` with `scanner.py` (ScannerBase subclass skeleton),
`config.yaml` (symbols, timeframes, correlations, paper settings), `main.py`
(live monitor), `backtest.py` (backtest entry point), and `transcripts/`.

The scaffold refuses to run if `traders/<name>/` already exists — it won't
clobber in-progress work.

---

## Phase 3: Implement Gates

### Step 3.1: Learn the available detectors

These are pure functions in `model_trader/detectors/` — no side effects,
operate on candle dicts:

| Function | Input | Returns | Purpose |
|----------|-------|---------|---------|
| `detect_swings` | `candles` | `list[Swing]` | pivot highs/lows |
| `detect_failure_swings` | `swings` | `list[FailureSwing]` | failed break attempts |
| `detect_fvg` | `candles, direction=None` | `list[FVG]` | fair value gaps |
| `update_fvg_states` | `fvgs, candles` | — | mark FVGs touched/filled |
| `detect_cisd` | `candles` | `list[CISDSignal]` | change in delivery |
| `detect_cisd_breaker` | `CISDSignals` | `list[Breaker]` | breakers of CISD |
| `detect_smt` | `primary_candles, correlated_candles` | `list[SMTSignal]` | SMT divergence |
| `detect_displacement` | `candles` | `list[Displacement]` | strong directional moves |

Read the detector source for exact argument shapes if unsure.

### Step 3.2: Understand the ScannerBase

```python
class ScannerBase(ABC):
    def __init__(self, config: dict, data_adapter):
        self.config = config
        self.data = data_adapter          # DataAdapter instance
        self.symbols = config["symbols"]
        self.timeframes = config.get("timeframes", ["1m","5m","15m","1h","4h"])
        self.correlations = config.get("correlations", {})

    def evaluate(self, symbol: str) -> SetupResult:  # YOU IMPLEMENT THIS
        ...

    def evaluate_at(self, symbol, hist, corr_hist, ts) -> SetupResult:  # AND THIS
        ...

    def fetch_data(self, symbol, extra_timeframes=None) -> dict[str, list[dict]]:
        ...

    def fetch_correlation(self, symbol, timeframes) -> dict[str, list[dict]]:
        ...
```

`config.yaml` provides symbols, timeframes, correlations, paper trading settings.

### Step 3.3: Translate strategy.md gates into code

Subclass `ScannerBase` in `traders/<name>/scanner.py`. Write gates as inline
pass/fail blocks inside `evaluate()` — there is no Gate class:

```python
from model_trader.gates import ScannerBase, SetupResult, SetupStatus
from model_trader.detectors import detect_swings, detect_fvg, ...

class Scanner(ScannerBase):
    def evaluate(self, symbol: str) -> SetupResult:
        result = SetupResult(symbol=symbol)
        data = self.fetch_data(symbol)
        corr_data = self.fetch_correlation(symbol, ["1h", "15m"])

        # GATE 1: [name] — [what it checks]
        if not some_condition:
            result.reason = "specific reason — shows in dashboard/journal"
            return result
        result.gates_passed.append("GATE_1_NAME")

        # GATE 2: ...
        # ...repeat for each gate...

        # FINAL GATE: compute levels, flip to TAKE
        result.direction = "long"          # or "short"
        result.entry = entry_price
        result.stop = stop_price
        result.target = target_price
        result.status = SetupStatus.TAKE
        result.reason = "All gates passed"
        return result
```

Gate design rules (see `docs/designing-gates.md` for full detail):
- One check per gate — split independent conditions
- Cheapest + most selective first — reject 95% at gate 1, not gate 5
- Always set `result.reason` on failure; always `gates_passed.append(name)` on pass
- Final gate sets entry, stop, target, direction → then `TAKE`
- 3-8 gates is typical; > 10 is over-engineered, < 3 is under-filtered
- Use `SKIP` for rejected setups; use `WAIT` only for the last 1-2 gates
  when the trader is waiting for one specific event

### Step 3.4: Implement `evaluate_at()` for backtesting

The backtest runner calls `evaluate_at(symbol, hist, corr_hist, ts)` with
pre-truncated history dicts. Factor gate logic into a shared helper:

```python
def _run_gates(self, symbol: str, data: dict, corr_data: dict) -> SetupResult:
    """All gate logic — shared by evaluate() and evaluate_at()."""
    result = SetupResult(symbol=symbol)
    # ... all gate checks here ...
    return result

def evaluate(self, symbol: str) -> SetupResult:
    data = self.fetch_data(symbol)
    corr_data = self.fetch_correlation(symbol, ["1h", "15m"])
    return self._run_gates(symbol, data, corr_data)

def evaluate_at(self, symbol: str, hist: dict, corr_hist: dict, ts: int) -> SetupResult:
    return self._run_gates(symbol, hist, corr_hist)
```

This way you write the gates once. See `docs/backtest.md`.

---

## Phase 4: Backtest

### Step 4.1: Run it

```bash
cd traders/<name>
uv run python backtest.py
```

The runner replays historical candles, simulating entries/exits with the same
SL/TP logic as the live paper trader. It auto-switches to ensemble mode if
`config.yaml` has an `ensemble:` section.

### Step 4.2: Interpret results

Output: trade count, win/loss, win rate %, total R, avg R, profit factor,
per-symbol breakdown.

What to check (in order):
1. **Trade count** — under ~10 over 7 days → gates too tight. Over ~200 → too loose.
   Aim for 1-5/day across all symbols.
2. **Win rate × avg R** — neither alone means anything. 40% WR with 2R avg is great.
   70% WR with 0.3R avg is mediocre. Profit factor > 1.2 is serviceable; > 1.5 is good.
3. **Per-symbol breakdown** — one symbol dominating = gates overfit to that symbol.
4. **Losing trades clustered?** Same symbol, direction, or time of day?
   That's where to iterate.

### Step 4.3: Provide a one-paragraph assessment

Tell the user:
- Whether the strategy is net profitable (profit factor > 1.0)
- Where the biggest leak is (e.g., "5 of 7 losses are shorts during an uptrend week")
- One concrete suggestion for the next gate tweak

---

## Phase 5: Iterate

The loop: `backtest → read results → identify one issue → tweak ONE gate → re-backtest`.

Never change multiple gates at once — you won't know which change mattered.

### Common issues and fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Too few trades (< 10/week) | Gates too strict | Loosen the most selective gate |
| Too many trades (> 200/week) | Gates too loose | Add a filter gate or tighten entry criteria |
| Win rate high, avg R low (< 0.5) | Stops too tight or targets too close | Widen stop to invalidation point; increase target |
| Win rate low, avg R high | Stops too wide or entries too late | Tighten stop; add confirmation gate before entry |
| All profits from one symbol | Overfit | Generalize the gate that's symbol-specific |
| Duplicate trades on same bar | Re-trigger bug | Filters should catch this; check `is_duplicate_setup` |
| Repeated stop-outs at same level | Level not invalidating | Add structural invalidation check; see `is_invalidated_level` |

### When to stop iterating

Stop when:
- 50+ closed trades in the journal
- Profit factor > 1.3 for two different backtest periods
- You understand WHY each losing trade lost (not just "it reversed" — which gate let it through?)

---

## Phase 6: Go Live (Paper)

```bash
cd traders/<name>
uv run python main.py
```

The monitor loop: check exits → scan all symbols → render dashboard → execute
TAKE setups (after duplicate/invalidated-level filters) → sleep.

All trades land in `traders/<name>/trades.json`. If an ensemble section is
configured in `config.yaml`, the monitor runs multi-scanner weighted voting
(see `docs/ensemble.md`).

---

## Reference: Key Types (verified against source)

```python
SetupStatus.TAKE     # all gates passed, execute
SetupStatus.WAIT     # forming, check again next scan
SetupStatus.SKIP     # rejected by a gate
SetupStatus.NO_SETUP # nothing interesting (default)

SetupResult:
    symbol: str
    status: SetupStatus
    direction: str | None      # "long" / "short"
    reason: str                # human-readable, shows in dashboard
    entry: float | None
    stop: float | None
    target: float | None
    gates_passed: list[str]    # which gates succeeded
    extras: dict               # free-form state (draw type, SMT status, etc.)
    timestamp: str             # ISO 8601, auto-set

Candle = {"timestamp": int_ms, "open": float, "high": float,
          "low": float, "close": float, "volume": float}
```

## Ensemble (multi-scanner voting)

Configure in `config.yaml` under `ensemble:`. Champion sets entry/stop/target;
challengers vote. Auto-promotion based on profit factor in `ensemble.db`.
See `docs/ensemble.md`.

---

## Gotchas

- **A `TAKE` with `entry=None` crashes the paper trader.** Final gate must set
  all four of entry/stop/target/direction.
- **Lookahead bias in `evaluate_at`.** Hist is pre-truncated to ≤ ts, but
  indexing forward (`data["1m"][i+1]`) still leaks — always slice backward from
  `[-1]`.
- **Same-bar SL+TP touch is scored as a LOSS.** Conservative simulator assumption
  — you can't know which side filled first intra-bar.
- **Gate-fail reason strings surface in the dashboard/journal.** Make them
  specific ("No HTF FVG within 50 bars"), never generic ("Filter rejected").
- **Don't score/weight conditions inside one scanner.** Pass/fail gates only.
  Weighted voting belongs at the ensemble layer (across multiple scanners).
- **`traders/` is gitignored.** Trader projects, trades.json, and ensemble.db
  are local-only.
