"""CachingDataAdapter — disk-backed cache wrapper for any DataAdapter.

Wraps a stateless inner adapter and persists historical candles to JSON so
repeated backtest runs avoid redundant network calls. Live trading path
(fetch_candles) is a pure passthrough with no I/O.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

from .base import Candle, DataAdapter


def _sanitize(symbol: str) -> str:
    """Replace any char outside [A-Za-z0-9] with underscore."""
    return re.sub(r"[^A-Za-z0-9]", "_", symbol)


class CachingDataAdapter(DataAdapter):
    """Decorator that adds disk caching around any DataAdapter.

    fetch_candles() — pure passthrough (live trading, no I/O).
    fetch_historical() — reads/writes a per-(adapter, symbol, timeframe)
    JSON cache under cache_dir. Atomic writes via temp-file + os.replace().
    """

    def __init__(self, inner: DataAdapter, cache_dir: Path | str) -> None:
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cache_path(self, symbol: str, timeframe: str) -> Path:
        adapter_name = type(self.inner).__name__
        filename = f"{adapter_name}_{_sanitize(symbol)}_{timeframe}.json"
        return self.cache_dir / filename

    def _read_cache(self, path: Path) -> dict | None:
        """Return parsed cache dict or None if the file does not exist."""
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return None

    def _write_cache(
        self,
        path: Path,
        candles: list[Candle],
        oldest_ts: int,
        newest_ts: int,
    ) -> None:
        """Atomically write cache file (temp + os.replace)."""
        payload = {
            "candles": candles,
            "oldest_ts": oldest_ts,
            "newest_ts": newest_ts,
        }
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)

    @staticmethod
    def _merge(cached: list[Candle], fresh: list[Candle]) -> list[Candle]:
        """Dict-union merge, fresh wins on collision, sorted ascending."""
        merged: dict[int, Candle] = {c["timestamp"]: c for c in cached}
        merged.update({c["timestamp"]: c for c in fresh})
        return sorted(merged.values(), key=lambda c: c["timestamp"])

    # ------------------------------------------------------------------
    # DataAdapter interface
    # ------------------------------------------------------------------

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
        """Pure passthrough — no caching on the live trading path."""
        return self.inner.fetch_candles(symbol, timeframe, limit)

    def fetch_historical(
        self,
        symbol: str,
        timeframe: str,
        days: int,
    ) -> list[Candle]:
        now_ms = int(time.time() * 1000)
        requested_oldest = now_ms - days * 86_400_000

        cache_path = self._cache_path(symbol, timeframe)
        cached = self._read_cache(cache_path)

        if cached is None or requested_oldest < cached["oldest_ts"]:
            # No cache, or window widened — full re-fetch.
            fresh = self.inner.fetch_historical(symbol, timeframe, days)
            existing: list[Candle] = cached["candles"] if cached is not None else []
            merged = self._merge(existing, fresh)
            if merged:
                oldest_ts = min(requested_oldest, merged[0]["timestamp"])
                newest_ts = merged[-1]["timestamp"]
            else:
                oldest_ts = requested_oldest
                newest_ts = now_ms
            self._write_cache(cache_path, merged, oldest_ts, newest_ts)
            all_candles = merged
        else:
            # Cache covers requested_oldest — only fetch the gap.
            # Compute the raw gap first; skip entirely if the cache is already
            # current (newest_ts >= now_ms, i.e. called twice within same run).
            raw_gap_days = math.ceil(
                (now_ms - cached["newest_ts"]) / 86_400_000
            )

            if raw_gap_days <= 0:
                # Cache is already fully fresh; skip the inner fetch entirely.
                all_candles = cached["candles"]
            else:
                gap_days = raw_gap_days + 1  # +1 for 1-day overlap to refresh in-progress candle
                fresh = self.inner.fetch_historical(symbol, timeframe, days=gap_days)
                merged = self._merge(cached["candles"], fresh)
                oldest_ts = cached["oldest_ts"]
                newest_ts = merged[-1]["timestamp"] if merged else cached["newest_ts"]
                self._write_cache(cache_path, merged, oldest_ts, newest_ts)
                all_candles = merged

        # Return candles in the requested window, oldest-first.
        return [
            c for c in all_candles
            if requested_oldest <= c["timestamp"] <= now_ms
        ]
