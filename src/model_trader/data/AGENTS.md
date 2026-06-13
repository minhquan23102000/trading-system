<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# data

## Purpose

Market data adapters. Provides the abstract `DataAdapter` base class for pluggable data sources (exchanges, APIs, historical databases) and a reference implementation (`HyperliquidAdapter`) for Hyperliquid's public perp exchange. Scanners, paper traders, and backtests use a `DataAdapter` instance to fetch OHLCV candles without caring where the data comes from.

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `DataAdapter` ABC with `fetch_candles()` and `fetch_historical()` contract; `Candle` TypedDict (timestamp, open, high, low, close, volume) |
| `hyperliquid.py` | `HyperliquidAdapter` — fetches OHLCV from Hyperliquid's public info endpoint; paginates ~500 candles per batch; supports native and synthetic perps |
| `__init__.py` | Exports `DataAdapter`, `Candle`, `HyperliquidAdapter` |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- **Stateless design**: DataAdapters should not cache candles or maintain state. Callers (backtester, monitor, scanner) manage their own caching if needed.
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

## HyperliquidAdapter Details

- **No authentication**: Uses Hyperliquid's fully public `/info` endpoint. No API key or secret required.
- **Supported timeframes**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w.
- **Candle batch size**: ~500 candles per HTTP request (API limit). Pagination handles requests larger than this by looping over `candleSnapshot`.
- **Symbol support**: Native perps (e.g., "BTC", "ETH") and synthetic perps deployed by builders (e.g., "xyz:GOLD", "xyz:SP500"). Pass the exact coin name as Hyperliquid defines it.
- **Deduplication**: Pagination can overlap at boundaries; adapter deduplicates by timestamp and returns `oldest-first` order.
- **Timeout**: Configurable per instance (default 10s). Pass custom `requests.Session` if you need connection pooling or proxy config.

## Dependencies

### Internal

None (base module; no upward deps into gates, detectors, or scanner).

### External

- `requests` (HTTP for candleSnapshot endpoint)
- `hyperliquid-python-sdk` (optional, for live executor use; data adapter only needs `requests`)

<!-- MANUAL: -->
