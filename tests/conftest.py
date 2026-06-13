"""Shared test fixtures for detector tests."""

from __future__ import annotations

import pytest


def _candle(ts: int, o: float, h: float, l: float, c: float, v: float = 1000) -> dict:
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}


# ── uptrend candles: clear higher highs and higher lows ──────────────
@pytest.fixture
def uptrend_candles() -> list[dict]:
    """10 candles in a clean uptrend — swings clearly visible."""
    return [
        _candle(0, 100, 102, 99, 101),
        _candle(1, 101, 104, 100, 103),
        _candle(2, 103, 106, 102, 105),  # HH, HL
        _candle(3, 105, 108, 104, 107),
        _candle(4, 107, 110, 106, 109),  # HH, HL
        _candle(5, 109, 112, 108, 111),
        _candle(6, 111, 114, 110, 113),  # HH, HL
        _candle(7, 113, 116, 112, 115),
        _candle(8, 115, 118, 114, 117),  # HH, HL
        _candle(9, 117, 120, 116, 119),
    ]


# ── downtrend candles: clear lower highs and lower lows ──────────────
@pytest.fixture
def downtrend_candles() -> list[dict]:
    """10 candles in a clean downtrend."""
    return [
        _candle(0, 120, 122, 119, 121),
        _candle(1, 121, 123, 118, 120),
        _candle(2, 120, 121, 117, 119),
        _candle(3, 119, 120, 116, 118),
        _candle(4, 118, 119, 115, 117),
        _candle(5, 117, 118, 114, 116),
        _candle(6, 116, 117, 113, 115),
        _candle(7, 115, 116, 112, 114),
        _candle(8, 114, 115, 111, 113),
        _candle(9, 113, 114, 110, 112),
    ]


# ── FVG candles: 3-candle gap pattern ────────────────────────────────
@pytest.fixture
def bullish_fvg_candles() -> list[dict]:
    """Candle 3's low is above candle 1's high — bullish FVG."""
    return [
        _candle(0, 100, 102, 99, 101),
        _candle(1, 101, 103, 100, 102),
        _candle(2, 105, 106, 104, 105),  # low(104) > high(102) → bullish FVG
    ]


@pytest.fixture
def bearish_fvg_candles() -> list[dict]:
    """Candle 3's high is below candle 1's low — bearish FVG."""
    return [
        _candle(0, 110, 112, 109, 111),
        _candle(1, 109, 110, 108, 109),
        _candle(2, 105, 106, 104, 105),  # high(106) < low(109) → bearish FVG
    ]


# ── swing-heavy candles for failure swing tests ──────────────────────
@pytest.fixture
def swing_list() -> list[dict]:
    """Swings detected from uptrend_candles with lookback=3."""
    return [
        {"type": "high", "price": 106, "index": 2, "strength": 2},
        {"type": "high", "price": 110, "index": 4, "strength": 2},
        {"type": "high", "price": 114, "index": 6, "strength": 2},
        {"type": "high", "price": 118, "index": 8, "strength": 2},
        {"type": "low", "price": 99, "index": 0, "strength": 2},
        {"type": "low", "price": 102, "index": 2, "strength": 2},
        {"type": "low", "price": 106, "index": 4, "strength": 2},
        {"type": "low", "price": 110, "index": 6, "strength": 2},
    ]


@pytest.fixture
def clustered_swings() -> list[dict]:
    """Swings with failures at similar levels."""
    return [
        {"type": "high", "price": 110.0, "index": 2},
        {"type": "high", "price": 110.1, "index": 5},   # near-identical to above — cluster
        {"type": "high", "price": 115.0, "index": 8},
        {"type": "low", "price": 100.0, "index": 1},
        {"type": "low", "price": 100.05, "index": 4},    # near-identical — cluster
        {"type": "low", "price": 95.0, "index": 7},
    ]


# ── displacement candles ─────────────────────────────────────────────
@pytest.fixture
def displacement_candles() -> list[dict]:
    """Last 3 candles are giant displacement moves."""
    candles = [
        _candle(i, 100 + i, 101 + i, 99 + i, 100.5 + i, 500)
        for i in range(7)
    ]
    # giant bullish candle
    candles.append(_candle(7, 107, 120, 105, 119, 2000))
    # giant bearish candle
    candles.append(_candle(8, 119, 121, 100, 101, 2000))
    return candles


# ── CISD candles + swings ────────────────────────────────────────────
@pytest.fixture
def cisd_candles() -> list[dict]:
    """Price breaks below recent swing low → bearish CISD."""
    return [
        _candle(0, 100, 102, 99, 101),
        _candle(1, 101, 103, 100, 102),
        _candle(2, 102, 105, 101, 104),   # swing high here
        _candle(3, 104, 106, 100, 101),
        _candle(4, 101, 103, 98, 99),
        _candle(5, 99, 100, 90, 91),      # closes below swing low
    ]


@pytest.fixture
def cisd_swings() -> list[dict]:
    """Swings for CISD test."""
    return [
        {"type": "low", "price": 99, "index": 0},
        {"type": "high", "price": 105, "index": 2},
    ]


# ── SMT swings ───────────────────────────────────────────────────────
@pytest.fixture
def smt_bearish_asset1() -> list[dict]:
    """Asset1 makes HH → bearish SMT when asset2 doesn't."""
    return [
        {"type": "high", "price": 110, "index": 2},
        {"type": "high", "price": 115, "index": 5},  # HH
        {"type": "low", "price": 100, "index": 1},
        {"type": "low", "price": 105, "index": 4},    # HL
    ]


@pytest.fixture
def smt_bearish_asset2() -> list[dict]:
    """Asset2 makes LH while asset1 makes HH → bearish SMT divergence."""
    return [
        {"type": "high", "price": 110, "index": 2},
        {"type": "high", "price": 108, "index": 5},  # LH — divergence!
        {"type": "low", "price": 100, "index": 1},
        {"type": "low", "price": 99, "index": 4},
    ]
