"""Tests for SMTDetector and detect_smt()."""

from model_trader.detectors import SMTDetector, detect_smt, SMTSignal


class TestSMTDetector:
    def test_detects_bearish_smt(self, smt_bearish_asset1, smt_bearish_asset2):
        detector = SMTDetector()
        signals = detector.detect(smt_bearish_asset1, smt_bearish_asset2)

        assert len(signals) == 1
        assert signals[0]["type"] == "bearish"

    def test_detects_bullish_smt(self):
        # Asset1 LL + Asset2 HL → bullish SMT
        asset1_swings = [
            {"type": "low", "price": 100, "index": 1},
            {"type": "low", "price": 95, "index": 4},   # LL
            {"type": "high", "price": 110, "index": 2},
            {"type": "high", "price": 105, "index": 5},  # not HH
        ]
        asset2_swings = [
            {"type": "low", "price": 100, "index": 1},
            {"type": "low", "price": 102, "index": 4},  # HL — divergence
            {"type": "high", "price": 110, "index": 2},
            {"type": "high", "price": 105, "index": 5},  # not HH (no bearish)
        ]
        detector = SMTDetector()
        signals = detector.detect(asset1_swings, asset2_swings)

        assert len(signals) == 1
        assert signals[0]["type"] == "bullish"

    def test_no_divergence(self):
        # Both assets make HH → no SMT signal
        asset1_swings = [
            {"type": "high", "price": 110, "index": 2},
            {"type": "high", "price": 115, "index": 5},
        ]
        asset2_swings = [
            {"type": "high", "price": 110, "index": 2},
            {"type": "high", "price": 115, "index": 5},
        ]

        detector = SMTDetector()
        signals = detector.detect(asset1_swings, asset2_swings)

        assert signals == []

    def test_empty_swings(self):
        detector = SMTDetector()
        signals = detector.detect([], [])

        assert signals == []

    def test_insufficient_swings(self):
        # Only 1 swing each — need >= 2 of same type
        asset1_swings = [
            {"type": "high", "price": 110, "index": 2},
        ]
        asset2_swings = [
            {"type": "high", "price": 110, "index": 2},
        ]

        detector = SMTDetector()
        signals = detector.detect(asset1_swings, asset2_swings)

        assert signals == []

    def test_legacy_wrapper(self, smt_bearish_asset1, smt_bearish_asset2):
        wrapper_result = detect_smt(smt_bearish_asset1, smt_bearish_asset2)
        instance_result = SMTDetector().detect(smt_bearish_asset1, smt_bearish_asset2)

        assert wrapper_result == instance_result

    def test_callable_instance(self, smt_bearish_asset1, smt_bearish_asset2):
        instance = SMTDetector()
        signals = instance(
            asset1_swings=smt_bearish_asset1,
            asset2_swings=smt_bearish_asset2,
        )

        assert len(signals) == 1
        assert signals[0]["type"] == "bearish"

    def test_name_attribute(self):
        assert SMTDetector.name == "smt"
