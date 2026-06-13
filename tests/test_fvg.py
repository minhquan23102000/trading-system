"""Tests for FVGDetector, detect_fvg(), and update_fvg_states()."""

from model_trader.detectors import FVGDetector, detect_fvg, update_fvg_states, FVG


def _c(ts: int, o: float, h: float, l: float, c: float) -> dict:
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": 1000}


class TestFVGDetector:
    def test_detects_bullish_fvg(self, bullish_fvg_candles):
        fvgs = FVGDetector().detect(bullish_fvg_candles)
        assert len(fvgs) == 1
        assert fvgs[0]["type"] == "bullish"
        assert fvgs[0]["filled"] is False

    def test_detects_bearish_fvg(self, bearish_fvg_candles):
        fvgs = FVGDetector().detect(bearish_fvg_candles)
        assert len(fvgs) == 1
        assert fvgs[0]["type"] == "bearish"

    def test_no_fvg_no_gap(self):
        candles = [
            _c(0, 100, 105, 95, 102),
            _c(1, 102, 104, 101, 103),
            _c(2, 101, 103, 100, 102),
        ]
        assert FVGDetector().detect(candles) == []

    def test_insufficient_candles(self):
        candles = [
            _c(0, 100, 102, 99, 101),
            _c(1, 101, 103, 100, 102),
        ]
        assert FVGDetector().detect(candles) == []

    def test_empty_candles(self):
        assert FVGDetector().detect([]) == []

    def test_legacy_wrapper(self, bullish_fvg_candles):
        assert detect_fvg(bullish_fvg_candles) == FVGDetector().detect(
            bullish_fvg_candles
        )

    def test_callable_instance(self, bullish_fvg_candles):
        detector = FVGDetector()
        assert detector(candles=bullish_fvg_candles) == detector.detect(
            bullish_fvg_candles
        )

    def test_update_fvg_filled(self, bullish_fvg_candles):
        fvgs = FVGDetector().detect(bullish_fvg_candles)
        assert fvgs[0]["filled"] is False
        # Append a candle whose low dips into the gap: fvg high=104
        candles = bullish_fvg_candles + [
            _c(3, 103, 105, 103, 104),
        ]
        update_fvg_states(fvgs, candles)
        assert fvgs[0]["filled"] is True

    def test_update_fvg_inversed(self, bullish_fvg_candles):
        fvgs = FVGDetector().detect(bullish_fvg_candles)
        # Append a candle that closes below gap: fvg low=102
        candles = bullish_fvg_candles + [
            _c(3, 103, 104, 99, 101),
        ]
        update_fvg_states(fvgs, candles)
        assert fvgs[0]["inversed"] is True

    def test_update_fvg_respected(self, bullish_fvg_candles):
        fvgs = FVGDetector().detect(bullish_fvg_candles)
        # Append a candle that dips into gap then closes above it
        candles = bullish_fvg_candles + [
            _c(3, 103, 106, 103, 105),
        ]
        update_fvg_states(fvgs, candles)
        assert fvgs[0]["respected"] is True

    def test_name_attribute(self):
        assert FVGDetector.name == "fvg"
