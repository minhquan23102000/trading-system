"""Yahoo Finance chart API adapter.

Uses the unofficial v8 chart endpoint. No API key required, but a browser-like
User-Agent header is required — Yahoo blocks the default python-requests UA.

Symbol mapping is required: pass a dict mapping framework symbols (e.g.
"xyz:GOLD") to Yahoo tickers (e.g. "GC=F").
"""

from __future__ import annotations

import time
import requests

from model_trader.logging import logger
from .base import DataAdapter, Candle


_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Supported timeframes -> Yahoo interval param
_TF_TO_YAHOO_INTERVAL: dict[str, str] = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "60m",  # Yahoo does not accept "1h"
    "4h":  "60m",  # fetched as 1h, then resampled
    "1d":  "1d",
}

# Supported timeframes -> max Yahoo range string
_TF_TO_RANGE: dict[str, str] = {
    "1m":  "7d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "1h":  "730d",
    "4h":  "730d",
    "1d":  "max",
}

# Approximate retention in seconds (for fetch_historical warning)
_TF_TO_MAX_SECONDS: dict[str, int] = {
    "1m":  7   * 86_400,
    "5m":  60  * 86_400,
    "15m": 60  * 86_400,
    "30m": 60  * 86_400,
    "1h":  730 * 86_400,
    "4h":  730 * 86_400,
    "1d":  20  * 365 * 86_400,  # "max" — effectively unlimited
}

_1H_MS = 3_600_000
_GAP_THRESHOLD_MS = int(_1H_MS * 1.5)  # >90 min gap => new group


class YahooFinanceAdapter(DataAdapter):
    """Fetches OHLCV data from Yahoo Finance's public v8 chart endpoint."""

    def __init__(
        self,
        symbol_map: dict[str, str],
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.symbol_map = symbol_map
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": _USER_AGENT})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
        """Return the most recent `limit` candles, oldest first."""
        candles = self._fetch_all(symbol, timeframe)
        return candles[-limit:]

    def fetch_historical(
        self,
        symbol: str,
        timeframe: str,
        days: int,
    ) -> list[Candle]:
        """Return candles covering the last `days` days, oldest first."""
        max_seconds = _TF_TO_MAX_SECONDS.get(timeframe)
        if max_seconds is not None and days * 86_400 > max_seconds:
            max_days = max_seconds // 86_400
            logger.warning(
                f"requested {days}d exceeds Yahoo's {max_days}d retention for "
                f"{timeframe}; returning available history only"
            )

        candles = self._fetch_all(symbol, timeframe)
        cutoff_ms = int(time.time() * 1000) - days * 86_400_000
        return [c for c in candles if c["timestamp"] >= cutoff_ms]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, symbol: str) -> str:
        ticker = self.symbol_map.get(symbol)
        if ticker is None:
            raise ValueError(f"no Yahoo mapping for symbol {symbol!r}")
        return ticker

    def _fetch_all(self, symbol: str, timeframe: str) -> list[Candle]:
        """Fetch all available candles for the max range for this timeframe."""
        if timeframe not in _TF_TO_YAHOO_INTERVAL:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")

        ticker = self._resolve(symbol)

        if timeframe == "4h":
            raw = self._fetch_yahoo(ticker, "60m", "730d")
            return self._resample_4h(raw)

        interval = _TF_TO_YAHOO_INTERVAL[timeframe]
        range_ = _TF_TO_RANGE[timeframe]
        return self._fetch_yahoo(ticker, interval, range_)

    def _fetch_yahoo(self, ticker: str, interval: str, range_: str) -> list[Candle]:
        """GET the Yahoo chart endpoint and parse into Candle list."""
        url = _CHART_URL.format(ticker=ticker)
        resp = self.session.get(
            url,
            params={"interval": interval, "range": range_},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        chart = data["chart"]
        if chart.get("error"):
            raise RuntimeError(f"Yahoo Finance error: {chart['error']}")

        result = chart["result"]
        if not result:
            return []

        result0 = result[0]
        timestamps = result0.get("timestamp") or []
        quote_list = result0.get("indicators", {}).get("quote") or []
        if not timestamps or not quote_list:
            return []

        quote = quote_list[0]
        opens   = quote.get("open")   or []
        highs   = quote.get("high")   or []
        lows    = quote.get("low")    or []
        closes  = quote.get("close")  or []
        volumes = quote.get("volume") or []

        candles: list[Candle] = []
        for i, ts in enumerate(timestamps):
            close = closes[i] if i < len(closes) else None
            if close is None:
                continue
            candles.append(
                Candle(
                    timestamp=ts * 1000,
                    open=float(opens[i]),
                    high=float(highs[i]),
                    low=float(lows[i]),
                    close=float(close),
                    volume=float(volumes[i] if i < len(volumes) and volumes[i] is not None else 0.0),
                )
            )

        return candles

    def _resample_4h(self, candles_1h: list[Candle]) -> list[Candle]:
        """Aggregate 1h candles into 4h bars with session-gap-aware grouping.

        A new group starts when:
        - the gap between consecutive candle timestamps exceeds 1.5 × 1h, OR
        - the current group already has 4 candles.
        Every group (even partial boundary groups) is emitted.
        """
        if not candles_1h:
            return []

        result: list[Candle] = []
        group: list[Candle] = [candles_1h[0]]

        for prev, curr in zip(candles_1h, candles_1h[1:]):
            gap = curr["timestamp"] - prev["timestamp"]
            if gap > _GAP_THRESHOLD_MS or len(group) == 4:
                result.append(_merge_group(group))
                group = [curr]
            else:
                group.append(curr)

        # Emit the trailing group regardless of size
        if group:
            result.append(_merge_group(group))

        return result


def _merge_group(group: list[Candle]) -> Candle:
    return Candle(
        timestamp=group[0]["timestamp"],
        open=group[0]["open"],
        high=max(c["high"] for c in group),
        low=min(c["low"] for c in group),
        close=group[-1]["close"],
        volume=sum(c["volume"] for c in group),
    )
