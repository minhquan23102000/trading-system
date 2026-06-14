"""Tests for CachingDataAdapter (no network required)."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest

from model_trader.data.base import Candle, DataAdapter
from model_trader.data.cache import CachingDataAdapter


# ---------------------------------------------------------------------------
# Fake adapter
# ---------------------------------------------------------------------------

class FakeAdapter(DataAdapter):
    def __init__(self) -> None:
        self.fetch_historical_calls: list[int] = []

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        return []

    def fetch_historical(self, symbol: str, timeframe: str, days: int) -> list[Candle]:
        self.fetch_historical_calls.append(days)
        now = int(time.time() * 1000)
        # One candle per day, oldest first.
        return [
            {
                "timestamp": now - i * 86_400_000,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
            }
            for i in range(days, -1, -1)
        ]


class AnotherFakeAdapter(FakeAdapter):
    """Distinct class name to verify cache filename differentiation."""
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCachingDataAdapter:

    def test_first_fetch_populates_cache_and_calls_inner_once(self, tmp_path: Path) -> None:
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        # Capture bounds BEFORE the fetch to avoid timing sensitivity:
        # FakeAdapter generates timestamps using its own time.time() call;
        # computing requested_oldest after the fact may shift by a few ms.
        now_ms_before = int(time.time() * 1000)
        result = adapter.fetch_historical("BTC", "1h", days=30)
        now_ms_after = int(time.time() * 1000)

        assert len(fake.fetch_historical_calls) == 1
        assert fake.fetch_historical_calls[0] == 30
        # Should have candles covering roughly 30 days (+1 boundary candle).
        assert len(result) >= 30
        # Allow 1-second slack at both ends for timing jitter.
        slack_ms = 1_000
        requested_oldest = now_ms_before - 30 * 86_400_000 - slack_ms
        assert all(requested_oldest <= c["timestamp"] <= now_ms_after + slack_ms for c in result)
        # Oldest-first order.
        timestamps = [c["timestamp"] for c in result]
        assert timestamps == sorted(timestamps)


    def test_second_call_same_days_no_redundant_full_refetch(self, tmp_path: Path) -> None:
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        adapter.fetch_historical("BTC", "1h", days=30)
        calls_after_first = len(fake.fetch_historical_calls)

        adapter.fetch_historical("BTC", "1h", days=30)
        calls_after_second = len(fake.fetch_historical_calls)

        # At most one additional inner call (the 1-day gap fetch).
        extra_calls = calls_after_second - calls_after_first
        assert extra_calls <= 1, (
            f"Expected at most 1 extra inner call, got {extra_calls}"
        )
        if extra_calls == 1:
            gap_days = fake.fetch_historical_calls[-1]
            assert gap_days <= 2, (
                f"Gap fetch should request ≤2 days, got {gap_days}"
            )

    def test_wider_window_triggers_full_refetch(self, tmp_path: Path) -> None:
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        # Prime the cache with 30 days.
        adapter.fetch_historical("BTC", "1h", days=30)

        # Request 90 days — wider than cache; must trigger a full re-fetch.
        result = adapter.fetch_historical("BTC", "1h", days=90)

        assert 90 in fake.fetch_historical_calls, (
            f"Expected a call with days=90; calls were {fake.fetch_historical_calls}"
        )

        now_ms = int(time.time() * 1000)
        requested_oldest_90 = now_ms - 90 * 86_400_000
        oldest_returned = min(c["timestamp"] for c in result)
        # Allow one-day of slack.
        assert oldest_returned <= requested_oldest_90 + 86_400_000, (
            "Returned candles should start at approximately now - 90 days"
        )

    def test_cache_filenames_differ_by_adapter_type(self, tmp_path: Path) -> None:
        fake1 = FakeAdapter()
        fake2 = AnotherFakeAdapter()

        adapter1 = CachingDataAdapter(fake1, cache_dir=tmp_path)
        adapter2 = CachingDataAdapter(fake2, cache_dir=tmp_path)

        adapter1.fetch_historical("BTC", "1h", days=5)
        adapter2.fetch_historical("BTC", "1h", days=5)

        files = list(tmp_path.glob("*.json"))
        names = {f.name for f in files}

        assert any("FakeAdapter_" in n for n in names), (
            f"Expected a FakeAdapter cache file; found {names}"
        )
        assert any("AnotherFakeAdapter_" in n for n in names), (
            f"Expected an AnotherFakeAdapter cache file; found {names}"
        )
        assert len(names) == 2, (
            f"Expected 2 distinct cache files; found {names}"
        )

    def test_fresh_wins_on_collision(self, tmp_path: Path) -> None:
        """A gap-fetch candle at timestamp T overwrites the stale cached value."""
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        # Manually seed the cache with a stale candle at a known timestamp.
        cache_path = tmp_path / "FakeAdapter_BTC_1h.json"
        now_ms = int(time.time() * 1000)
        stale_ts = now_ms - 1 * 86_400_000  # 1 day ago — within gap-fetch range

        # oldest_ts is 10 days ago (so requested 5-day window is covered),
        # but newest_ts is yesterday so a gap fetch will include stale_ts.
        seed = {
            "candles": [
                {
                    "timestamp": now_ms - 10 * 86_400_000,
                    "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
                },
                {
                    "timestamp": stale_ts,
                    "open": 999.0, "high": 999.0, "low": 999.0, "close": 999.0, "volume": 1.0,
                },
            ],
            "oldest_ts": now_ms - 10 * 86_400_000,
            "newest_ts": stale_ts,
        }
        cache_path.write_text(json.dumps(seed), encoding="utf-8")

        # Override fetch_historical to return a candle at stale_ts with close=1.0.
        def fresh_fetch(symbol: str, timeframe: str, days: int) -> list[Candle]:
            return [
                {
                    "timestamp": stale_ts,
                    "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
                }
            ]

        fake.fetch_historical = fresh_fetch  # type: ignore[method-assign]

        result = adapter.fetch_historical("BTC", "1h", days=5)

        # Find the candle at stale_ts.
        matching = [c for c in result if c["timestamp"] == stale_ts]
        assert matching, f"Expected a candle at ts={stale_ts}; result={result}"
        assert matching[0]["close"] == 1.0, (
            f"Fresh value should win (1.0) but got {matching[0]['close']}"
        )

    def test_fetch_candles_passthrough(self, tmp_path: Path) -> None:
        """fetch_candles must delegate directly to inner with no disk I/O."""
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        result = adapter.fetch_candles("BTC", "1h", limit=10)

        assert result == []
        # No cache files should have been created.
        assert list(tmp_path.glob("*.json")) == []

    def test_symbol_sanitization_in_cache_filename(self, tmp_path: Path) -> None:
        """Symbols with colons/special chars are sanitized in cache filenames."""
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        adapter.fetch_historical("xyz:GOLD", "1h", days=5)

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        # Colon should be replaced with underscore.
        assert "xyz_GOLD" in files[0].name
        assert ":" not in files[0].name

    def test_gap_days_zero_skips_inner_fetch(self, tmp_path: Path) -> None:
        """If gap_days <= 0, inner adapter must NOT be called again."""
        fake = FakeAdapter()
        adapter = CachingDataAdapter(fake, cache_dir=tmp_path)

        adapter.fetch_historical("BTC", "1h", days=30)
        calls_before = len(fake.fetch_historical_calls)

        # Manually set newest_ts to now so gap_days == 0.
        cache_path = tmp_path / "FakeAdapter_BTC_1h.json"
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        now_ms = int(time.time() * 1000)
        data["newest_ts"] = now_ms + 1  # in the future → gap_days will be ≤ 0
        cache_path.write_text(json.dumps(data), encoding="utf-8")

        adapter.fetch_historical("BTC", "1h", days=30)

        assert len(fake.fetch_historical_calls) == calls_before, (
            "Inner adapter should NOT be called when gap_days <= 0"
        )
