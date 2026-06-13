<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# detectors

## Purpose

Pure-function pattern detectors for price-action trading signals. Each detector is a stateless class that analyzes candlestick data and returns typed events (swings, gaps, divergences, etc.). Detectors are the building blocks: strategies combine them to form scanner entry/exit setups. All detectors inherit from the base `Detector` contract and are callable (instance or legacy function form).

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `Detector` ABC: abstract `detect()` method, `name` class variable, `__call__` convenience wrapper |
| `swings.py` | `SwingDetector` — identifies swing highs/lows; returns list of `Swing` with price/index/strength |
| `fvg.py` | `FVGDetector` — detects fair-value gaps (3-candle patterns); includes `update_fvg_states()` for fill tracking |
| `failure_swings.py` | `FailureSwingDetector` — clusters swings within tolerance; identifies multiple touches at same level |
| `cisd.py` | `CISDDetector` — detects swing breaks (change in state of delivery); `detect_cisd_breaker()` finds the confirmation candle |
| `smt.py` | `SMTDetector` — divergence detector comparing swing structures across correlated assets |
| `displacement.py` | `DisplacementDetector` — identifies large/aggressive candles (size ratio relative to average) |
| `__init__.py` | Public API: exports detector classes, legacy functions, and type definitions |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **Detector contract**: Every detector inherits from `Detector` (base.py) and implements `detect(**kwargs) -> list[dict]`.
- **Configuration in `__init__`**: Store thresholds (lookback, tolerance, multipliers) as instance variables. Detectors are **stateless after init** — calling `detect()` multiple times with different inputs must not mutate shared state.
- **Input contract**: Candle list is a list of dicts with keys `timestamp`, `open`, `high`, `low`, `close`, `volume`. Some detectors accept multiple candle lists or swing lists as input.
- **Output contract**: Each detector returns a list of typed dicts (TypedDict). Every return type is defined in the same file (e.g., `Swing`, `FVG`, `CISDSignal`).
- **Legacy compatibility**: Original function wrappers (e.g., `detect_swings()`, `detect_fvg()`) are kept for backward compat but delegate to detector instances. New code should prefer the class form.
- **No I/O or side effects**: Detectors are pure functions over candle/swing lists. No file I/O, logging, or external calls.
- **Callable instances**: Use `detector.detect(candles)` or equivalently `detector(candles)` thanks to `__call__`.

### Testing Requirements

Tests live in `tests/test_<detector>.py` (e.g., `tests/test_swings.py`, `tests/test_fvg.py`). Each test file imports the detector class and legacy function:
```python
from model_trader.detectors import SwingDetector, detect_swings, Swing
```

Test structure:
- Basic detection: verify output shape and required fields.
- Edge cases: empty input, single candle, exact boundary values.
- Type consistency: returned dicts match the TypedDict schema (use `TypedDict` for static checks).

Run via `uv run pytest tests/test_*.py -v`.

### Common Patterns

- **Candle indexing**: Candles are indexed from start of list. Some detectors look back (`candles[-self.lookback:]`) relative to the end; store absolute indices for later reference.
- **Swing-dependent detectors**: `FailureSwingDetector`, `CISDDetector`, and `SMTDetector` accept swing lists as input (output from `SwingDetector`). They assume swings include at least `type`, `price`, and `index` fields.
- **Multiple asset inputs**: `SMTDetector.detect(asset1_swings, asset2_swings)` compares structures across two correlated assets.
- **State tracking**: `FVGDetector` returns FVGs with initial `filled=False`, `inversed=False`, `respected=False`. Call `update_fvg_states(fvgs, candles)` to update based on subsequent price action.
- **Type annotations**: All return types are TypedDicts; input kwargs should be typed for IDE support.

## Detector Reference

### SwingDetector

**Class**: `SwingDetector(lookback: int = 3)`

**Method**: `detect(candles: list[dict]) -> list[Swing]`

**Purpose**: Identifies swing highs (local maxima) and swing lows (local minima) using a symmetric lookback window.

**Logic**: A swing high at index `i` requires the high at `i` to be greater than all highs within `lookback` candles on both sides. Swing lows are the inverse (lower lows on both sides).

**Output Type** (`Swing` TypedDict):
```
type: str          # 'high' or 'low'
price: float       # price of the swing (candles[i]["high"] or candles[i]["low"])
index: int         # absolute index in the candle list
strength: int      # number of confirming candles on each side (= lookback)
```

**Example**:
```python
detector = SwingDetector(lookback=3)
swings = detector.detect(candles)
# [{type='high', price=100.5, index=10, strength=3}, ...]
```

### FVGDetector

**Class**: `FVGDetector()`

**Method**: `detect(candles: list[dict]) -> list[FVG]`

**Purpose**: Detects fair-value gaps — price inefficiencies where a 3-candle sequence leaves a gap unfilled between candle 1 and candle 3.

**Logic**: 
- **Bullish FVG**: `candle[i-2].high < candle[i].low` (gap above)
- **Bearish FVG**: `candle[i-2].low > candle[i].high` (gap below)

**Output Type** (`FVG` TypedDict):
```
type: str          # 'bullish' or 'bearish'
high: float        # upper bound of the gap
low: float         # lower bound of the gap
candle_index: int  # index of candle 3 (where gap is formed)
timestamp: str     # from candle 2 (candle_index - 1)
filled: bool       # true if price has entered the gap
inversed: bool     # true if price closed through the gap without filling it
respected: bool    # true if filled but then reversed back through the gap
```

**Helper**: `update_fvg_states(fvgs: list[FVG], candles: list[dict]) -> list[FVG]`
Updates `filled`, `inversed`, and `respected` flags based on subsequent candles.

**Example**:
```python
detector = FVGDetector()
fvgs = detector.detect(candles)
# [{type='bullish', high=100.0, low=99.5, candle_index=5, timestamp='...', 
#   filled=False, inversed=False, respected=False}, ...]
updated = update_fvg_states(fvgs, candles)  # mark filled/inversed/respected
```

### FailureSwingDetector

**Class**: `FailureSwingDetector(tolerance_pct: float = 0.1)`

**Method**: `detect(swings: list[dict]) -> list[FailureSwing]`

**Purpose**: Clusters swings that touch the same price level, indicating strong liquidity attraction. Multiple failures at a level increase conviction.

**Logic**: Groups swings of the same type (`high` or `low`) where price difference ≤ `tolerance_pct / 100` of the first swing's price. Returns clusters with ≥2 members.

**Input**: List of swing dicts (output from `SwingDetector` or equivalent). Must include `type` and `price` fields.

**Output Type** (`FailureSwing` TypedDict):
```
level: float       # average price of all swings in the cluster
count: int         # number of swings in the cluster
type: str          # 'high' or 'low' (all swings in cluster have same type)
```

**Example**:
```python
detector = FailureSwingDetector(tolerance_pct=0.1)  # 0.1% tolerance
failure_swings = detector.detect(swings)
# [{level=100.2, count=3, type='high'}, {level=99.8, count=2, type='low'}]
```

### CISDDetector

**Class**: `CISDDetector()`

**Method**: `detect(candles: list[dict], swings: list[dict]) -> list[CISDSignal]`

**Purpose**: Detects change in state of delivery — when a recent swing high or low is broken, signaling a structural shift. Looks at the 3 most recent swings of each type.

**Logic**: 
- **Bearish CISD**: Current close is below the lowest recent swing low.
- **Bullish CISD**: Current close is above the highest recent swing high.

**Output Type** (`CISDSignal` TypedDict):
```
type: str           # 'bullish' or 'bearish'
broken_level: float # the swing price that was broken
swing_index: int    # candle index of the broken swing
```

**Helper**: `detect_cisd_breaker(candles: list[dict], cisd_signal: CISDSignal | None) -> Breaker | None`
Finds the confirmation candle that forms after CISD (a strong candle in the opposite direction of the CISD, up to 10 candles before the swing).

**Output Type** (`Breaker` TypedDict):
```
type: str   # 'bullish_breaker' or 'bearish_breaker'
high: float
low: float
index: int  # candle index of the breaker
```

**Example**:
```python
detector = CISDDetector()
signals = detector.detect(candles, swings)
# [{type='bearish', broken_level=99.5, swing_index=8}]
breaker = detect_cisd_breaker(candles, signals[0])
# Breaker(type='bearish_breaker', high=101.0, low=100.5, index=5)
```

### SMTDetector

**Class**: `SMTDetector()`

**Method**: `detect(asset1_swings: list[dict], asset2_swings: list[dict]) -> list[SMTSignal]`

**Purpose**: Detects smart money technique divergences by comparing swing structures across two correlated assets. When one asset makes a higher high but the other doesn't, it signals a divergence (potential reversal).

**Logic**:
- **Bearish SMT**: Asset 1 makes a higher high, but asset 2 does not (last 5 swings examined).
- **Bullish SMT**: Asset 1 makes a lower low, but asset 2 does not.
- **Strength**: "strong" if the most recent swing indices are within 3 candles; "weak" otherwise.

**Input**: Two lists of swing dicts. Each must include at least `type`, `price`, and `index` fields.

**Output Type** (`SMTSignal` TypedDict):
```
type: str       # 'bullish' or 'bearish'
strength: str   # 'strong' or 'weak' (based on temporal proximity of swings)
```

**Example**:
```python
detector = SMTDetector()
signals = detector.detect(btc_swings, eth_swings)
# [{type='bearish', strength='strong'}, ...]
```

### DisplacementDetector

**Class**: `DisplacementDetector(lookback: int = 5, threshold_multiplier: float = 2.0)`

**Method**: `detect(candles: list[dict]) -> list[Displacement]`

**Purpose**: Identifies aggressive, strong candles (size significantly larger than recent average). Used to detect momentum or capitulation.

**Logic**: 
1. Calculate average candle size (absolute value of close − open) over the 3×lookback candles prior to the lookback window.
2. For each candle in the last `lookback` candles, if its size > average × `threshold_multiplier`, mark it as a displacement.

**Output Type** (`Displacement` TypedDict):
```
index: int          # absolute candle index
direction: str      # 'bullish' if close > open, else 'bearish'
size_ratio: float   # current candle size / average size
```

**Example**:
```python
detector = DisplacementDetector(lookback=5, threshold_multiplier=2.0)
displacements = detector.detect(candles)
# [{index=48, direction='bullish', size_ratio=2.5}, ...]
```

## Dependencies

### Internal

- `base.Detector` — abstract base class all detectors inherit from.
- Detectors do not import each other; they are independent.
- Callers assemble detectors (e.g., `gates/` or trader scanners) and chain their outputs.

### External

- Python standard library only (`typing`, `abc`).

<!-- MANUAL: -->
