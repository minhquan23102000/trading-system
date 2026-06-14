"""Live integration tests for BinanceAdapter.

All tests hit the real Binance public REST API.
Run with: uv run pytest tests/test_data_binance.py -v
"""

import pytest

from model_trader.data.binance import BinanceAdapter


@pytest.mark.network
class TestBinanceAdapterLive:
    """Integration tests that require a network connection."""

    def setup_method(self):
        self.adapter = BinanceAdapter()

    # ------------------------------------------------------------------
    # fetch_candles
    # ------------------------------------------------------------------

    def test_fetch_candles_returns_correct_count(self):
        candles = self.adapter.fetch_candles("BTC", "5m", limit=10)
        assert len(candles) == 10

    def test_fetch_candles_oldest_first(self):
        candles = self.adapter.fetch_candles("BTC", "5m", limit=10)
        timestamps = [c["timestamp"] for c in candles]
        assert timestamps == sorted(timestamps), "Candles must be oldest-first"

    def test_fetch_candles_fields_are_float(self):
        candles = self.adapter.fetch_candles("BTC", "5m", limit=10)
        for c in candles:
            assert isinstance(c["open"],   float), f"open is {type(c['open'])}, expected float"
            assert isinstance(c["high"],   float)
            assert isinstance(c["low"],    float)
            assert isinstance(c["close"],  float)
            assert isinstance(c["volume"], float)

    def test_fetch_candles_timestamp_is_int(self):
        candles = self.adapter.fetch_candles("BTC", "5m", limit=10)
        for c in candles:
            assert isinstance(c["timestamp"], int)

    def test_fetch_candles_open_is_not_str(self):
        """Guard against returning raw Binance strings instead of floats."""
        candles = self.adapter.fetch_candles("BTC", "5m", limit=5)
        assert not isinstance(candles[0]["open"], str), (
            "open field must be float, not str — Binance returns strings in raw JSON"
        )

    # ------------------------------------------------------------------
    # ValueError on unsupported timeframe
    # ------------------------------------------------------------------

    def test_unsupported_timeframe_raises(self):
        with pytest.raises(ValueError, match="unsupported timeframe"):
            self.adapter.fetch_candles("BTC", "7m")

    def test_unsupported_timeframe_message_includes_value(self):
        with pytest.raises(ValueError, match="'7m'"):
            self.adapter.fetch_candles("XYZ", "7m")

    # ------------------------------------------------------------------
    # fetch_historical — multi-year pagination
    # ------------------------------------------------------------------

    def test_fetch_historical_multi_year(self):
        """400 days of daily candles must yield well over 300 rows."""
        candles = self.adapter.fetch_historical("BTC", "1d", days=400)
        assert len(candles) > 300, (
            f"Expected >300 candles for 400-day window, got {len(candles)}"
        )

    def test_fetch_historical_oldest_first(self):
        candles = self.adapter.fetch_historical("BTC", "1d", days=400)
        timestamps = [c["timestamp"] for c in candles]
        assert timestamps == sorted(timestamps)

    def test_fetch_historical_no_duplicates(self):
        candles = self.adapter.fetch_historical("BTC", "1d", days=400)
        timestamps = [c["timestamp"] for c in candles]
        assert len(timestamps) == len(set(timestamps)), "Duplicate timestamps found"

    def test_fetch_historical_fields_are_float(self):
        candles = self.adapter.fetch_historical("BTC", "1d", days=10)
        for c in candles:
            assert isinstance(c["open"],  float)
            assert isinstance(c["close"], float)
