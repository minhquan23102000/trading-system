"""Trading: paper-trading engine, shared journal/sizing primitives, and live executors.

The PaperTrader persists to a JSON journal so state survives restarts.
Filters (duplicate detection, invalidated level tracking) plug into the
monitor loop to prevent common failure modes (scalp duplicates, cascades).

`journal` holds the persistence, position-sizing, and close/PnL math shared
with live executors, plus the `Trader` structural protocol both `PaperTrader`
and `live.HyperliquidExecutor` satisfy.

`live` contains exchange-specific order-execution adapters (e.g.
`HyperliquidExecutor`). Imported lazily so the core package has no hard
dependency on exchange SDKs — `from model_trader.trading.live import
HyperliquidExecutor`.
"""

from .paper import PaperTrader, Trade
from .filters import is_duplicate_setup, is_invalidated_level
from .metrics import calculate_metrics
from .journal import Trader, apply_close, load_journal, save_journal, size_with_leverage_cap

__all__ = [
    "PaperTrader",
    "Trade",
    "Trader",
    "is_duplicate_setup",
    "is_invalidated_level",
    "calculate_metrics",
    "apply_close",
    "load_journal",
    "save_journal",
    "size_with_leverage_cap",
]
