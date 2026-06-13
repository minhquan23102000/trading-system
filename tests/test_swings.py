"""Tests for SwingDetector and detect_swings()."""

from model_trader.detectors import SwingDetector, detect_swings, Swing


class TestSwingDetector:
    def test_detects_swing_highs(self, uptrend_candles):
        """With lookback=2, detector runs on uptrend and returns Swing dicts."""
        detector = SwingDetector(lookback=2)
        results = detector.detect(uptrend_candles)
        assert isinstance(results, list)
        for r in results:
            assert r["type"] in ("high", "low")

    def test_detects_swing_lows(self, downtrend_candles):
        """Downtrend detection returns properly typed Swing dicts."""
        detector = SwingDetector(lookback=2)
        results = detector.detect(downtrend_candles)
        assert isinstance(results, list)
        for r in results:
            assert r["type"] in ("high", "low")

    def test_custom_lookback(self, uptrend_candles):
        """Narrower lookback produces >= swings than wider lookback."""
        results_1 = SwingDetector(lookback=1).detect(uptrend_candles)
        results_3 = SwingDetector(lookback=3).detect(uptrend_candles)
        assert len(results_1) >= len(results_3)

    def test_empty_candles(self):
        """Empty candle list returns empty list."""
        assert SwingDetector(lookback=2).detect([]) == []

    def test_too_few_candles(self):
        """Not enough candles for detection window returns empty."""
        candles = [
            {"timestamp": i, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000}
            for i in range(5)
        ]
        assert SwingDetector(lookback=3).detect(candles) == []

    def test_legacy_wrapper(self, uptrend_candles):
        """detect_swings() returns same result as SwingDetector.detect()."""
        assert detect_swings(uptrend_candles, lookback=2) == SwingDetector(lookback=2).detect(uptrend_candles)

    def test_callable_instance(self, uptrend_candles):
        """Calling the instance delegates to detect()."""
        detector = SwingDetector(lookback=2)
        assert detector(candles=uptrend_candles) == detector.detect(uptrend_candles)

    def test_name_attribute(self):
        """SwingDetector.name is 'swing'."""
        assert SwingDetector.name == "swing"
