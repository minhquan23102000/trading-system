"""Tests for failure swing detector."""

from __future__ import annotations

from model_trader.detectors import FailureSwingDetector, detect_failure_swings


class TestFailureSwingDetector:
    def test_detects_clusters(self, clustered_swings):
        detector = FailureSwingDetector()
        result = detector.detect(clustered_swings)
        assert len(result) >= 2

    def test_no_clusters_no_duplicates(self):
        swings = [
            {"type": "high", "price": 100.0, "index": 0},
            {"type": "high", "price": 110.0, "index": 1},
            {"type": "high", "price": 120.0, "index": 2},
            {"type": "high", "price": 130.0, "index": 3},
        ]
        detector = FailureSwingDetector()
        result = detector.detect(swings)
        assert result == []

    def test_empty_input(self):
        detector = FailureSwingDetector()
        result = detector.detect([])
        assert result == []

    def test_single_swing(self):
        swings = [{"type": "high", "price": 100.0, "index": 0}]
        detector = FailureSwingDetector()
        result = detector.detect(swings)
        assert result == []

    def test_custom_tolerance(self):
        swings = [
            {"type": "high", "price": 100.0, "index": 0},
            {"type": "high", "price": 104.0, "index": 1},
        ]
        detector = FailureSwingDetector(tolerance_pct=5.0)
        result = detector.detect(swings)
        assert len(result) == 1
        assert result[0]["count"] == 2
        assert result[0]["type"] == "high"
        assert abs(result[0]["level"] - 102.0) < 0.01

    def test_legacy_wrapper(self, clustered_swings):
        result_direct = FailureSwingDetector().detect(clustered_swings)
        result_wrapper = detect_failure_swings(clustered_swings)
        assert result_direct == result_wrapper

    def test_callable_instance(self, clustered_swings):
        detector = FailureSwingDetector()
        result_call = detector(swings=clustered_swings)
        result_detect = detector.detect(clustered_swings)
        assert result_call == result_detect

    def test_name_attribute(self):
        assert FailureSwingDetector.name == "failure_swing"
