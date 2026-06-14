"""Binance public REST API adapter.

Uses the spot klines endpoint — no API key required for market data.
Symbol convention: pass the base asset ("BTC", "ETH"); USDT quote is appended
automatically (e.g. "BTC" → "BTCUSDT").
"""

from __future__ import annotations

import time
import requests

from .base import DataAdapter, Candle


_KLINES_URL = "https://api.binance.com/api/v3/klines"

# Supported timeframe strings (Binance interval strings match framework strings)
_SUPPORTED_TF = frozenset({
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w",
})

# Milliseconds per timeframe — for startTime pagination
_TF_MS: dict[str, int] = {
    "1m":  60_000,
    "3m":  180_000,
    "5m":  300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h":  3_600_000,
    "2h":  7_200_000,
    "4h":  14_400_000,
    "6h":  21_600_000,
    "8h":  28_800_000,
    "12h": 43_200_000,
    "1d":  86_400_000,
    "3d":  259_200_000,
    "1w":  604_800_000,
}

_BATCH_SIZE = 1000


class BinanceAdapter(DataAdapter):
    """Fetches OHLCV data from Binance's public spot klines endpoint."""

    def __init__(
        self,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
        """Return the most recent *limit* candles, oldest first.

        Args:
            symbol: Base asset ticker, e.g. "BTC". "USDT" is appended.
            timeframe: Interval string — must be one of the supported set.
            limit: Max candles to return (capped at 1000).

        Raises:
            ValueError: If *timeframe* is not supported.
        """
        if timeframe not in _SUPPORTED_TF:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")

        rows = self._get_with_retry({
            "symbol": f"{symbol.upper()}USDT",
            "interval": timeframe,
            "limit": min(limit, _BATCH_SIZE),
        })
        return [_row_to_candle(r) for r in rows]

    def fetch_historical(
        self,
        symbol: str,
        timeframe: str,
        days: int,
    ) -> list[Candle]:
        """Paginate klines to cover *days* of history.

        Stops when a batch returns fewer than 1 000 rows (hit present or
        listing date) or when startTime advances past now.

        Args:
            symbol: Base asset ticker, e.g. "BTC".
            timeframe: Interval string — must be one of the supported set.
            days: Look-back window in calendar days.

        Returns:
            Candles with timestamp >= now - days*86_400_000, oldest first,
            deduplicated by timestamp.
        """
        if timeframe not in _SUPPORTED_TF:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")

        interval_ms = _TF_MS[timeframe]
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - days * 86_400_000

        all_candles: list[Candle] = []
        start_ms = cutoff_ms
        sym = f"{symbol.upper()}USDT"

        while start_ms < now_ms:
            rows = self._get_with_retry({
                "symbol": sym,
                "interval": timeframe,
                "startTime": start_ms,
                "limit": _BATCH_SIZE,
            })
            if not rows:
                break

            for r in rows:
                all_candles.append(_row_to_candle(r))

            if len(rows) < _BATCH_SIZE:
                # Reached the present or asset listing date
                break

            start_ms = all_candles[-1]["timestamp"] + interval_ms

            # Courtesy pause between pagination requests
            time.sleep(0.05)

        # Deduplicate and sort
        seen: set[int] = set()
        unique: list[Candle] = []
        for c in sorted(all_candles, key=lambda c: c["timestamp"]):
            if c["timestamp"] not in seen:
                seen.add(c["timestamp"])
                unique.append(c)

        # Trim to requested window
        return [c for c in unique if c["timestamp"] >= cutoff_ms]

    def _get_with_retry(self, params: dict, max_retries: int = 4) -> list:
        """GET _KLINES_URL with params, retrying on HTTP 429."""
        delay = 1.0
        for attempt in range(max_retries + 1):
            resp = self.session.get(_KLINES_URL, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                if attempt == max_retries:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else delay
                time.sleep(wait)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        return []  # unreachable


def _row_to_candle(row: list) -> Candle:
    """Map a Binance kline array row to a Candle dict."""
    return {
        "timestamp": int(row[0]),
        "open":      float(row[1]),
        "high":      float(row[2]),
        "low":       float(row[3]),
        "close":     float(row[4]),
        "volume":    float(row[5]),
    }
