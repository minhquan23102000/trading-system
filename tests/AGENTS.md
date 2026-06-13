<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# tests

## Purpose
Unit tests for detector implementations in `model_trader.detectors`. Each test file focuses on a single detector class and its behavior across normal cases, edge cases, and state transitions. Fixtures provide reusable candle and swing data patterns.

## Key Files
| File | Description |
|------|-------------|
| `conftest.py` | Shared pytest fixtures: candle sequences (`uptrend_candles`, `downtrend_candles`, `displacement_candles`, `cisd_candles`), FVG patterns (`bullish_fvg_candles`, `bearish_fvg_candles`), swing fixtures (`swing_list`, `clustered_swings`, `smt_bearish_asset1`, `smt_bearish_asset2`, `cisd_swings`). Helper: `_candle(ts, o, h, l, c, v)` → candle dict. |
| `test_swings.py` | SwingDetector: detects higher highs/lows in trends; tests lookback parameter, empty input, callable interface, legacy `detect_swings()` wrapper. |
| `test_fvg.py` | FVGDetector: identifies 3-candle gap patterns (bullish: low > high; bearish: high < low). Tests detection, filled/inversed/respected state transitions via `update_fvg_states()`, legacy `detect_fvg()` wrapper. |
| `test_displacement.py` | DisplacementDetector: flags candles with range > historical average × threshold. Configurable `lookback` and `threshold_multiplier`. Tests direction (bullish/bearish), custom thresholds, edge cases. |
| `test_failure_swings.py` | FailureSwingDetector: clusters swings within tolerance (e.g., two highs at ~110 → one failure level). Tests clustering, tolerance parameter, legacy `detect_failure_swings()` wrapper. |
| `test_cisd.py` | CISDDetector: detects breaks of recent swing levels; bullish when close > swing high, bearish when close < swing low. Tests both directions, `detect_cisd_breaker()` helper. Legacy `detect_cisd()` wrapper. |
| `test_smt.py` | SMTDetector: multi-timeframe analysis — detects divergence between two assets (e.g., asset1 HH but asset2 LH → bullish SMT). Tests bearish/bullish/no-signal cases, legacy `detect_smt()` wrapper. |

## Subdirectories
None.

## For AI Agents

### Working In This Directory
- **Pytest config**: `testpaths = ["tests"]`, `pythonpath = ["src"]` (from `pyproject.toml`). Run `uv run pytest` from repo root.
- **Fixture naming**: Each detector has dedicated fixtures (e.g., `uptrend_candles` for swings, `bullish_fvg_candles` for FVG). Reuse existing fixtures; add new ones to `conftest.py` with clear docstrings.
- **Test class structure**: One `TestDetectorName` class per detector; test methods are prefixes `test_*`.
- **Detector interface**: All detectors follow the pattern:
  - Constructor takes optional config (e.g., `lookback`, `tolerance_pct`).
  - `.detect(...)` returns a list of signal dicts.
  - Callable: `detector(...)` delegates to `.detect()`.
  - `.name` class attribute: lowercase detector name (e.g., `"swing"`, `"fvg"`).
- **Legacy wrappers**: Module-level functions (e.g., `detect_swings()`, `detect_fvg()`) tested alongside class methods to ensure parity.
- **Candle dict**: `{"timestamp": int, "open": float, "high": float, "low": float, "close": float, "volume": float}`. Use `_candle(ts, o, h, l, c, v=1000)` from conftest.

### Testing Requirements
- Run: `uv run pytest` from repo root.
- Detector changes **require** a test update or new test in the corresponding `test_<detector>.py` file.
- All tests must pass before merging detector PRs.
- Test coverage: normal operation, edge cases (empty input, insufficient data), parameter variations, state transitions (for stateful detectors like FVG).

### Common Patterns
- **Fixture reuse**: `uptrend_candles`, `downtrend_candles` used by swing tests; `displacement_candles` for displacement tests.
- **Stateful detectors**: FVG has `filled`, `inversed`, `respected` flags. Use `update_fvg_states(fvgs, candles)` to advance state and test transitions.
- **Two-asset detectors**: SMT compares two swing lists; both fixtures (`smt_bearish_asset1`, `smt_bearish_asset2`) provide divergence.
- **Clustering**: Failure swing detector groups swings near the same level (tolerance default 2%); test with `clustered_swings` fixture.
- **CISD helper**: `detect_cisd_breaker(candles, signal)` finds the candle that breaks the CISD level; tested separately.

## Dependencies

### Internal
- `model_trader.detectors` — all detector classes and wrapper functions

### External
- `pytest>=8.0` (dev extra in `pyproject.toml`)

<!-- MANUAL: -->
