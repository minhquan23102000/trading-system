# Adding a Data Source

The framework ships with `HyperliquidAdapter` (no API key, public Hyperliquid
`/info` endpoint), `BinanceAdapter` (public Binance spot klines, years of
history for crypto), and `YahooFinanceAdapter` (public Yahoo Finance chart
API, for `xyz:`-style synthetic equity/futures proxies). To trade other
markets — Bybit, CCXT-compatible exchanges, brokers, custom feeds — you
write a new `DataAdapter` subclass.

## The contract

```python
from model_trader.data import DataAdapter, Candle

class MyAdapter(DataAdapter):
    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        ...
```

That's the whole interface. One method. The returned list must:

- Be **oldest-first** (most recent candle is `result[-1]`)
- Contain **dicts** with keys: `timestamp` (Unix ms), `open`, `high`, `low`,
  `close`, `volume`
- Have **at most `limit`** candles
- Use **the timeframes the framework speaks**: `1m`, `3m`, `5m`, `15m`,
  `30m`, `1h`, `2h`, `4h`, `1d`. If your source uses different keys, map
  them inside the adapter.

The base class provides a default `fetch_historical(symbol, timeframe, days)`
that just calls `fetch_candles` with a computed limit. If your data source
caps responses (most do), override `fetch_historical` to paginate — see
`HyperliquidAdapter` for an example.

## Minimal example: CCXT

```python
import ccxt
from model_trader.data import DataAdapter

class CCXTAdapter(DataAdapter):
    TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m",
              "1h": "1h", "4h": "4h", "1d": "1d"}

    def __init__(self, exchange_id: str = "binance"):
        self.client = getattr(ccxt, exchange_id)()

    def fetch_candles(self, symbol, timeframe, limit=200):
        tf = self.TF_MAP[timeframe]
        raw = self.client.fetch_ohlcv(symbol, tf, limit=limit)
        return [
            {"timestamp": ts, "open": o, "high": h, "low": l,
             "close": c, "volume": v}
            for ts, o, h, l, c, v in raw
        ]
```

Wire it into your trader's `main.py`:

```python
from my_adapter import CCXTAdapter

data = CCXTAdapter("binance")
scanner = Scanner(config, data)
```

## Things to handle

- **Symbol naming.** `BTC` on Hyperliquid is `BTC/USDT` on Binance, `BTCUSD`
  on Coinbase. Either translate inside the adapter or set canonical symbols
  in your `config.yaml`.
- **Timeframe support.** If your exchange doesn't expose `3m`, raise
  `ValueError` rather than silently returning the wrong timeframe.
- **Pagination.** Most APIs cap at 500-1000 candles per call. For
  `fetch_historical(days=30)` on `1m` you need ~43k candles, which means
  multiple paginated calls glued together (oldest first, deduplicated).
- **Rate limits.** The live monitor scans every `scan_interval` seconds
  across N symbols, hitting all timeframes. If your exchange rate-limits
  aggressively, add a token bucket or `time.sleep()` inside the adapter.
- **Auth.** The `__init__` is the place for API keys. Read from env vars,
  not hardcoded.

## Things NOT to do

- **Don't cache in a source adapter.** `HyperliquidAdapter`, `BinanceAdapter`,
  and `YahooFinanceAdapter` are stateless except for config/clients — they
  make a fresh request every call. **Wrapper adapters are the exception**:
  `CachingDataAdapter` (`model_trader.data.cache`) decorates any stateless
  source adapter and persists `fetch_historical()` results to disk so
  repeated backtest runs only fetch the gap since the last run. This is the
  recommended pattern for backtests — wrap, don't reimplement caching inside
  a source adapter. `fetch_candles()` (the live-trading path) stays a pure
  passthrough even when wrapped.
- **Don't transform candles.** No fillNaN, no smoothing, and no resampling
  across non-contiguous data — `YahooFinanceAdapter`'s `4h` is the one
  sanctioned exception: it aggregates *contiguous* native `1h` bars (no gap
  > 1.5h) into real 4h OHLCV bars, never fabricating a bar from missing data.
  The detectors expect raw OHLC. If your source has dirty data, fix the
  source.
- **Don't return synthetic candles.** If a candle is missing, skip it. Don't
  fabricate one — the gates make decisions based on real bars only.
- **Don't return more than `limit`.** It will work but it'll waste time and
  memory across thousands of scans.

## Testing your adapter

```python
adapter = MyAdapter()
candles = adapter.fetch_candles("BTC", "5m", limit=10)
assert len(candles) <= 10
assert all("timestamp" in c for c in candles)
assert candles == sorted(candles, key=lambda c: c["timestamp"])  # oldest first
```

Then plug it into a scanner and run the live monitor for a few minutes. If
the dashboard shows symbols progressing through gates and prices that look
reasonable for the market, you're done.
