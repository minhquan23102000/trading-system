<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# gates

## Purpose
Gate framework that defines the scanner base class and result types for the gate pattern. A scanner evaluates a symbol through a sequence of pass/fail gates and produces a `SetupResult` with a `SetupStatus`. See `docs/designing-gates.md` for guidance on mapping a trader's rules to a gate sequence.

## Key Files
| File | Description |
|------|-------------|
| `base.py` | `ScannerBase` ABC, `SetupResult` dataclass, `SetupStatus` enum |
| `__init__.py` | Public exports: `ScannerBase`, `SetupResult`, `SetupStatus` |

## Subdirectories
None.

## For AI Agents

### Working In This Directory

**ScannerBase** is the abstract base class for trading scanners. Subclass it to implement a trader's strategy.

#### ScannerBase abstract methods
- **`evaluate(symbol: str) -> SetupResult`** — Run the full gate pipeline for one symbol. Implementations should:
  1. Fetch candle data for each configured timeframe (use `fetch_data()`)
  2. Run gates in order, returning early on failure
  3. Only produce `TAKE` if all gates pass and `entry`/`stop`/`target` are set

#### ScannerBase concrete methods and helpers
- **`__init__(config: dict, data_adapter)`** — Store config and adapter. Extracts `symbols`, `timeframes`, `correlations` from config.
- **`scan_all() -> list[SetupResult]`** — Evaluate every symbol in the config.
- **`fetch_data(symbol: str, extra_timeframes: list[str] | None = None) -> dict`** — Helper to fetch all configured timeframes for a symbol. Returns `{timeframe: [Candle]}`. Missing timeframes become empty lists for safe downstream `data.get(tf)` checks.
- **`fetch_correlation(symbol: str, timeframes: list[str]) -> dict`** — Helper to fetch correlation pair data if configured in the scanner's config. Returns `{timeframe: [Candle]}` for the correlation symbol.

**SetupResult** is the output of evaluating one symbol through the scanner. Only `TAKE` results are actionable and reach the paper trader.

#### SetupResult fields
| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `symbol` | `str` | — | Required. The symbol being evaluated. |
| `status` | `SetupStatus` | `NO_SETUP` | One of `TAKE`, `WAIT`, `SKIP`, or `NO_SETUP`. |
| `direction` | `str \| None` | `None` | Optional. Either `"long"` or `"short"` for actionable setups. |
| `reason` | `str` | `""` | Human-readable explanation, especially important for `SKIP` and `WAIT`. |
| `entry` | `float \| None` | `None` | Entry price. Must be set for `TAKE` results. |
| `stop` | `float \| None` | `None` | Stop-loss price. Must be set for `TAKE` results. |
| `target` | `float \| None` | `None` | Target/take-profit price. Must be set for `TAKE` results. |
| `gates_passed` | `list[str]` | `[]` | Names of gates that passed (for dashboard and debugging). |
| `extras` | `dict[str, Any]` | `{}` | Free-form dict for strategy-specific state (draw type, variation name, SMT status, etc.) to log or pass to the paper trader. |
| `timestamp` | `str` | Auto-generated ISO8601 | When this result was created. |

**SetupStatus** is a string enum with four values.

#### SetupStatus values
| Value | Meaning |
|-------|---------|
| `TAKE` | All gates passed. Setup is valid and ready to execute. Must have `entry`, `stop`, `target`, and `direction` set. |
| `WAIT` | Setup is forming but not actionable yet (e.g., waiting for LTF trigger, CISD candle, or retrace to entry zone). Check again on the next scan. Rendered distinctly on the dashboard. |
| `SKIP` | Setup is actively rejected (a gate failed, structure broken, competing draws, etc.). The setup is dead; move on to the next symbol. |
| `NO_SETUP` | No candidate of interest on this symbol right now. Default status. Not rendered in the dashboard. |

### Testing Requirements
- Detector tests in `tests/test_*.py` import detectors and verify they work correctly.
- Scanner implementations are tested via `backtest.py` (historical replay) or live `run_monitor()` (dashboard).
- To verify a custom scanner works: run `python backtest.py` for historical validation, then `run_monitor()` for live signals.

### Common Patterns

**Every gate must log its result:**
```python
if condition_failed:
    result.reason = "Specific reason (e.g., 'No HTF FVG within 50 bars')"
    return result
result.gates_passed.append("GATE_NAME")
```

**Gate ordering: cheap and selective first.** Filters that reject 95% of setups before expensive I/O calls make the scanner faster.

**Final gate sets levels and flips to TAKE:**
```python
result.entry = entry_price
result.stop = stop_price
result.target = target_price
result.direction = direction  # "long" or "short"
result.status = SetupStatus.TAKE
result.reason = "All gates passed"
return result
```

**For backtesting, implement `evaluate_at(symbol: str, hist: dict, corr_hist: dict, ts: int) -> SetupResult`** — same gate logic as `evaluate()` but reading from passed-in history dicts instead of calling the data adapter. See `docs/backtest.md`.

## Dependencies

### Internal
- `model_trader.data` — `DataAdapter` for fetching candles in `fetch_data()` and `fetch_correlation()`
- `model_trader.detectors` — Pattern detection functions called by gates (swings, FVG, CISD, SMT, displacement, failure swings)

### External
- `dataclasses` (stdlib) — `@dataclass`, `field()`
- `abc` (stdlib) — `ABC`, `@abstractmethod`
- `datetime` (stdlib) — timestamp generation
- `enum` (stdlib) — `Enum`

<!-- MANUAL: -->
