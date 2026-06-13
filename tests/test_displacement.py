"""Tests for DisplacementDetector and detect_displacement()."""

from __future__ import annotations

from model_trader.detectors import DisplacementDetector, detect_displacement


class TestDisplacementDetector:
    def test_detects_displacement(self, displacement_candles):
        result = DisplacementDetector(lookback=5, threshold_multiplier=2.0).detect(
            displacement_candles
        )
        assert len(result) >= 1

    def test_no_displacement_normal_candles(self, uptrend_candles):
        result = DisplacementDetector(lookback=5, threshold_multiplier=2.0).detect(
            uptrend_candles
        )
        assert result == []

    def test_empty_candles(self):
        result = DisplacementDetector().detect([])
        assert result == []

    def test_direction_bullish(self, displacement_candles):
        result = DisplacementDetector(lookback=5, threshold_multiplier=2.0).detect(
            displacement_candles
        )
        assert any(d["direction"] == "bullish" for d in result)

    def test_direction_bearish(self, displacement_candles):
        result = DisplacementDetector(lookback=5, threshold_multiplier=2.0).detect(
            displacement_candles
        )
        assert any(d["direction"] == "bearish" for d in result)

    def test_custom_threshold(self, displacement_candles):
        result = DisplacementDetector(
            lookback=5, threshold_multiplier=100
        ).detect(displacement_candles)
        assert result == []

    def test_legacy_wrapper(self, displacement_candles):
        class_result = DisplacementDetector(
            lookback=5, threshold_multiplier=2.0
        ).detect(displacement_candles)
        legacy_result = detect_displacement(
            displacement_candles, lookback=5, threshold_multiplier=2.0
        )
        assert class_result == legacy_result

    def test_callable_instance(self, displacement_candles):
        detector = DisplacementDetector(lookback=5, threshold_multiplier=2.0)
        result = detector(candles=displacement_candles)
        assert len(result) >= 1

    def test_name_attribute(self):
        assert DisplacementDetector.name == "displacement"
