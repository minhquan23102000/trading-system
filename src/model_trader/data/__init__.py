"""Market data adapters.

To add a new exchange or data source, subclass `DataAdapter` and implement
`fetch_candles()`. Your scanner and paper trader only need a DataAdapter
instance — they don't care where the data comes from.
"""

from .base import DataAdapter, Candle
from .hyperliquid import HyperliquidAdapter
from .binance import BinanceAdapter
from .yahoo import YahooFinanceAdapter
from .cache import CachingDataAdapter

__all__ = [
    "DataAdapter",
    "Candle",
    "HyperliquidAdapter",
    "BinanceAdapter",
    "YahooFinanceAdapter",
    "CachingDataAdapter",
]
