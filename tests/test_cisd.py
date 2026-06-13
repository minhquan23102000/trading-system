"""Tests for CISDDetector, detect_cisd(), and detect_cisd_breaker()."""

from model_trader.detectors import (
    CISDDetector,
    detect_cisd,
    detect_cisd_breaker,
    CISDSignal,
    Breaker,
)


def _candle(ts: int, o: float, h: float, l: float, c: float) -> dict:
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": 1000}


class TestCISDDetector:
    def test_detects_bearish_cisd(self, cisd_candles, cisd_swings):
        detector = CISDDetector()
        signals = detector.detect(cisd_candles, cisd_swings)
        assert len(signals) == 1
        assert signals[0]["type"] == "bearish"
        assert signals[0]["broken_level"] == 99
        assert signals[0]["swing_index"] == 0

    def test_detects_bullish_cisd(self):
        candles = [
            _candle(0, 100, 102, 99, 101),
            _candle(1, 101, 104, 100, 103),
            _candle(2, 103, 110, 102, 108),
        ]
        swings = [{"type": "high", "price": 105, "index": 1}]
        detector = CISDDetector()
        signals = detector.detect(candles, swings)
        assert len(signals) == 1
        assert signals[0]["type"] == "bullish"
        assert signals[0]["broken_level"] == 105
        assert signals[0]["swing_index"] == 1

    def test_no_break_no_signal(self, cisd_candles, cisd_swings):
        candles = [dict(c) for c in cisd_candles]
        candles[-1]["close"] = 100
        detector = CISDDetector()
        signals = detector.detect(candles, cisd_swings)
        assert signals == []

    def test_empty_swings(self, cisd_candles):
        detector = CISDDetector()
        signals = detector.detect(cisd_candles, [])
        assert signals == []

    def test_legacy_wrapper(self, cisd_candles, cisd_swings):
        assert detect_cisd(cisd_candles, cisd_swings) == CISDDetector().detect(
            cisd_candles, cisd_swings
        )

    def test_callable_instance(self, cisd_candles, cisd_swings):
        detector = CISDDetector()
        result = detector(candles=cisd_candles, swings=cisd_swings)
        assert len(result) == 1
        assert result[0]["type"] == "bearish"

    def test_breaker_bearish(self):
        candles = [
            _candle(0, 100, 102, 99, 98),
            _candle(1, 101, 105, 100, 104),
            _candle(2, 104, 108, 102, 103),
        ]
        signal = CISDSignal(type="bearish", broken_level=100, swing_index=2)
        breaker = detect_cisd_breaker(candles, signal)
        assert breaker is not None
        assert breaker["type"] == "bearish_breaker"
        assert breaker["index"] == 1

    def test_breaker_none_when_none_signal(self):
        candles = [_candle(0, 100, 102, 99, 101)]
        assert detect_cisd_breaker(candles, None) is None

    def test_name_attribute(self):
        assert CISDDetector.name == "cisd"
