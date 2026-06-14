<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# data

## Purpose

Market data adapters. Provides the abstract `DataAdapter` base class for pluggable data sources (exchanges, APIs, historical databases), reference implementations (`HyperliquidAdapter`, `BinanceAdapter`, `YahooFinanceAdapter`), and a caching decorator (`CachingDataAdapter`). Scanners, paper traders, and backtests use a `DataAdapter` instance to fetch OHLCV candles without caring where the data comes from.

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `DataAdapter` ABC with `fetch_candles()` and `fetch_historical()` contract; `Candle` TypedDict (timestamp, open, high, low, close, volume) |
| `hyperliquid.py` | `HyperliquidAdapter` — fetches OHLCV from Hyperliquid's public info endpoint; paginates ~500 candles per batch; supports native and synthetic perps |
| `binance.py` | `BinanceAdapter` — fetches OHLCV from Binance's public spot klines endpoint (no key); paginates 1000 candles per batch; years of history for crypto majors |
| `yahoo.py` | `YahooFinanceAdapter` — fetches OHLCV from Yahoo Finance's public v8 chart endpoint via a required `symbol_map`; `4h` is synthesized by session-gap-aware aggregation of native `1h` bars |
| `cache.py` | `CachingDataAdapter` — disk-backed caching decorator around any `DataAdapter`; `fetch_candles()` passthrough, `fetch_historical()` caches/merges/dedupes to JSON under a caller-supplied `cache_dir` |
| `__init__.py` | Exports `DataAdapter`, `Candle`, `HyperliquidAdapter`, `BinanceAdapter`, `YahooFinanceAdapter`, `CachingDataAdapter` |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **Stateless source adapters**: `HyperliquidAdapter`/`BinanceAdapter`/`YahooFinanceAdapter` must not cache candles or maintain state — every call hits the network. **Wrapper adapters are the sanctioned exception**: `CachingDataAdapter` decorates a stateless source adapter and persists `fetch_historical()` to disk (`fetch_candles()` stays a pure passthrough). Use the wrapper for backtests; don't add caching inside a source adapter.
- **Candle shape is canonical**: All adapters must return `Candle` dicts with all six fields (timestamp in Unix ms, all prices and volume as floats). Missing or extra keys break downstream code.
- **Symbol format**: Exchange-specific. Hyperliquid uses "BTC", "ETH" for natives; "xyz:GOLD" format for synthetic perps. Document your adapter's symbol conventions.
- **Timeframe strings**: Standardized ("1m", "5m", "15m", "1h", "4h", "1d"). The adapter maps these to exchange-native intervals if needed (see `_TF_MAP` in `hyperliquid.py`).

### Testing Requirements

No dedicated test file yet. Manual integration tests via backtest (`uv run python -m model_trader.backtest`) or paper trader confirm data adapters work end-to-end with a scanner.

### Common Patterns

- **fetch_candles()** returns the most recent `limit` candles; callers expect oldest-first order.
- **fetch_historical()** has a default implementation (uses `fetch_candles` with large limit); override if your adapter supports pagination for longer lookbacks.
- **Timeframe mapping**: If your exchange uses different interval strings, map them at init or in a lookup table (like `_TF_MAP` in HyperliquidAdapter).
- **Pagination**: Large requests may exceed API limits; split into batches and deduplicate by timestamp (HyperliquidAdapter handles this via `_fetch_range`).

## Adapter Details

### HyperliquidAdapter
- **No authentication**: Uses Hyperliquid's fully public `/info` endpoint. No API key or secret required.
- **Supported timeframes**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w.
- **Candle batch size**: ~500 candles per HTTP request (API limit). Pagination handles requests larger than this by looping over `candleSnapshot`.
- **Symbol support**: Native perps (e.g., "BTC", "ETH") and synthetic perps deployed by builders (e.g., "xyz:GOLD", "xyz:SP500"). Pass the exact coin name as Hyperliquid defines it.
- **Deduplication**: Pagination can overlap at boundaries; adapter deduplicates by timestamp and returns `oldest-first` order.
- **Retention ceiling**: `candleSnapshot` caps each response at ~5000 *most-recent* candles per (coin, interval) — hard server-side limit. `5m`≈17d, `15m`≈52d, `1h`≈208d, `4h`≈833d. `endTime` older than the ceiling returns `[]`; no adapter or cache can recover data the server no longer has.
- **Timeout**: Configurable per instance (default 10s). Pass custom `requests.Session` if you need connection pooling or proxy config.

### BinanceAdapter
- **No authentication**: Public spot klines endpoint (`/api/v3/klines`). Symbol convention: pass the base asset (`"BTC"`); `USDT` is appended (`"BTCUSDT"`).
- **Supported timeframes**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w — raises `ValueError` on anything else.
- **Retention**: years of history at every supported interval for major pairs (BTC/ETH since 2017-08-17, SOL since 2020-08-11, AVAX since 2020-09-22).
- **Pagination**: 1000 candles/request via `startTime`; stops at present or asset listing date. Deduplicates by timestamp.
- **Retry**: 429 responses retried with `Retry-After`/exponential backoff via `_get_with_retry`.

### YahooFinanceAdapter
- **No authentication**, but requires a browser-like `User-Agent` header (Yahoo blocks the default `python-requests` UA).
- **Required `symbol_map`**: maps framework symbols (e.g. `"xyz:GOLD"`) to Yahoo tickers (e.g. `"GC=F"`). Unmapped symbol -> `ValueError`.
- **Supported timeframes**: 1m, 5m, 15m, 30m, 1h, 4h, 1d — raises `ValueError` on anything else.
- **Retention**: `5m`/`15m`/`30m`≈60d, `1h`≈730d, `1d`=full history. `fetch_historical(days=N)` beyond a timeframe's retention logs a warning and returns the available history (does not raise).
- **`4h` is synthetic**: Yahoo has no native 4h interval. The adapter fetches native `1h` bars (730d) and aggregates *contiguous* runs (gap ≤ 1.5h) into 4h OHLCV bars — session/day boundaries start a new group rather than merging across the gap. Every emitted 4h bar is a real aggregate of 1-4 real 1h bars; none are fabricated.
- **Units**: Yahoo returns Unix-second timestamps; the adapter multiplies by 1000 for the `Candle` contract (ms).

## Dependencies

### Internal

None (base module; no upward deps into gates, detectors, or scanner).

### External

- `requests` (HTTP for all three source adapters)
- `hyperliquid-python-sdk` (optional, for live executor use; data adapters only need `requests`)

<!-- MANUAL: -->
