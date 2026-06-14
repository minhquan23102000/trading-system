"""Integration tests for YahooFinanceAdapter.

All tests in this file make live HTTP requests to Yahoo Finance.
Run with:   uv run pytest tests/test_data_yahoo.py -v
"""

import pytest

from model_trader.data.yahoo import YahooFinanceAdapter


_ADAPTER = YahooFinanceAdapter(
    symbol_map={
        "xyz:GOLD":  "GC=F",
        "xyz:SP500": "^GSPC",
    }
)


@pytest.mark.network
def test_fetch_candles_gold_1h_returns_10():
    candles = _ADAPTER.fetch_candles("xyz:GOLD", "1h", limit=10)

    assert len(candles) == 10, f"expected 10 candles, got {len(candles)}"
    for c in candles:
        assert c["timestamp"] > 10**12, "timestamp must be in milliseconds"
        assert isinstance(c["open"],   float)
        assert isinstance(c["high"],   float)
        assert isinstance(c["low"],    float)
        assert isinstance(c["close"],  float)
        assert isinstance(c["volume"], float)

    # oldest-first ordering
    timestamps = [c["timestamp"] for c in candles]
    assert timestamps == sorted(timestamps), "candles must be oldest-first"


@pytest.mark.network
def test_fetch_historical_sp500_4h_ohlc_integrity():
    candles = _ADAPTER.fetch_historical("xyz:SP500", "4h", days=10)

    assert len(candles) > 0, "expected at least one 4h candle for SP500 in 10 days"

    for c in candles:
        assert c["high"] >= c["open"],  f"high < open: {c}"
        assert c["high"] >= c["close"], f"high < close: {c}"
        assert c["high"] >= c["low"],   f"high < low: {c}"
        assert c["low"]  <= c["open"],  f"low > open: {c}"
        assert c["low"]  <= c["close"], f"low > close: {c}"

    timestamps = [c["timestamp"] for c in candles]
    assert timestamps == sorted(timestamps), "candles must be sorted ascending"
    assert len(timestamps) == len(set(timestamps)), "duplicate timestamps found"


@pytest.mark.network
def test_unmapped_symbol_raises():
    with pytest.raises(ValueError, match="no Yahoo mapping for symbol"):
        _ADAPTER.fetch_candles("xyz:NOPE", "1h", limit=5)


@pytest.mark.network
def test_unsupported_timeframe_raises():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        _ADAPTER.fetch_candles("xyz:GOLD", "7m", limit=5)
