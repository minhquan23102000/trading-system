<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-13 | Updated: 2026-06-13 -->

# trading.live

## Purpose

Live order execution adapters. Provides exchange-agnostic executor interfaces and concrete implementations for placing real orders. Currently ships with `HyperliquidExecutor` for live margin trading on Hyperliquid. The framework's core (`PaperTrader`, `run_monitor`, backtest) is paper-trading only; executors are optional modules traders use when they want to go live. Executors are imported on-demand so the main package has no hard dependency on exchange SDKs.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Lazy exports; currently just `HyperliquidExecutor` via `__getattr__` to avoid eager SDK imports |
| `hyperliquid.py` | `HyperliquidExecutor` — places limit entries + exchange-side SL/TP triggers on Hyperliquid testnet or mainnet; manages a JSON journal of live trades; reconciles fills via `check_exits()` |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

**HyperliquidExecutor** is a live order executor for Hyperliquid perpetual markets. Key design:

- **Separate journal**: Executors maintain their own JSON journal distinct from the paper trader's. This allows parallel live and paper trading for comparison, or independent live-only deployments.
- **Two-phase order strategy**: Entry is a limit order (can linger); SL and TP are exchange-side triggers so they execute even if the bot is offline.
- **Stateless between calls**: Executor reads its journal from disk, performs reconciliation, writes back. No in-memory cache.
- **Testnet-first**: Default to testnet; pass `testnet=False` for mainnet. Never hardcode a mainnet key; always use env vars.
- **Size and price rounding**: Hyperliquid has specific rounding rules (max 5 significant figures for prices, size decimals per asset). Executor handles this transparently.
- **Multi-dex support**: Hyperliquid supports builder-deployed synth perps (e.g., "xyz:GOLD") on separate margin accounts. Executor discovers all dexes at init and queries the correct account per coin.
- **Shared sizing/PnL math**: Position sizing (`size_with_leverage_cap`) and close accounting (`apply_close`) come from `..journal` (`model_trader.trading.journal`) — the same functions `PaperTrader` uses. Don't re-derive this math locally; fix it in `..journal` so paper and live stay in sync.

#### HyperliquidExecutor public API

```python
HyperliquidExecutor(
    journal_path: str | Path,
    wallet_address: str,           # Main wallet (holds margin)
    api_private_key: str,          # API wallet private key (trade-only)
    testnet: bool = True,          # Route to testnet API
    per_trade_pct: float = 1.0,    # Risk per trade as % of account
    max_leverage: float = 25.0,    # Cap notional to balance * this
)
```

**Methods:**

- **`execute(setup: dict) -> dict | None`** — Open a trade from a TAKE `SetupResult`. Expects keys: `status`, `symbol`, `direction`, `entry`, `stop`, `target`. Returns the journal entry dict (with `id`, `entry_oid`, `sl_oid`, `tp_oid`, `status`, `fill_time`, etc.) or `None` if rejected.
  - Validates setup completeness and calculates position size from risk budget via `..journal.size_with_leverage_cap()`.
  - Caps position via `max_leverage` to prevent over-leveraging.
  - Places three orders atomically: entry limit, TP trigger, SL trigger (grouped as `normalTpsl`).
  - Journal entry is marked `PENDING` until entry fills, then `OPEN`.

- **`check_exits() -> list[dict]`** — Reconcile open trades against exchange state (open orders, positions, fills). Called periodically by the monitor loop or your main script.
  - Marks `PENDING` trades as `OPEN` once entry fills, or `CANCELLED` if the entry order was rejected.
  - Marks `OPEN` trades as `CLOSED` (via `..journal.apply_close()`) when no position remains (TP or SL triggered, or manual close).
  - Queries all registered dexes (native perp + builder perps) to handle multi-account portfolios.
  - Returns the list of newly-closed trades.

- **`get_open_trades() -> list[dict]`** — List trades with status `OPEN` or `PENDING`.

- **`get_all_trades() -> list[dict]`** — List all trades in the journal (including closed).

- **`get_balance(coin: str | None = None) -> float`** — Margin available on the target dex (default dex if `coin` is omitted). Native perps query dex=""; synth perps route to the builder's dex based on the coin name (e.g., "xyz:GOLD" → dex="xyz").

#### Journal format

Each trade entry is a dict:

```python
{
    "id": str,                      # 8-char UUID suffix
    "symbol": str,                  # Coin name (e.g., "BTC", "xyz:GOLD")
    "direction": str,               # "long" or "short"
    "entry_price": float,           # Filled or limit price
    "stop_loss": float,             # Rounded SL price
    "take_profit": float,           # Rounded TP price
    "position_size": float,         # Rounded contract size
    "risk_amount": float,           # Risk in USDC (% of account)
    "rr_ratio": float,              # Target distance / risk distance
    "entry_oid": int | None,        # Exchange order ID for entry
    "sl_oid": int | None,           # Exchange order ID for SL trigger
    "tp_oid": int | None,           # Exchange order ID for TP trigger
    "status": str,                  # PENDING, OPEN, CANCELLED, CLOSED
    "entry_time": str,              # ISO8601 when order was placed
    "fill_time": str | None,        # ISO8601 when entry filled
    "exit_time": str | None,        # ISO8601 when position closed
    "exit_price": float | None,     # Actual fill price at close
    "pnl": float | None,            # Exit price - entry price (per contract)
    "r_multiple": float | None,     # (Exit - entry) / risk distance
    "outcome": str | None,          # "WIN" / "LOSS" / None
    "notes": str,                   # "TP_HIT" / "SL_HIT" / "ENTRY_CANCELLED" / etc.
    "extras": dict,                 # Any extra fields from the original SetupResult
}
```

### Testing Requirements

No dedicated test file. Manual integration testing via:
1. **Testnet**: Deploy to testnet with real Hyperliquid API key and small per_trade_pct (e.g., 0.1).
2. **Live monitoring**: Call `check_exits()` every scan interval to confirm fills and closes are reconciled correctly.
3. **Journal inspection**: Verify the JSON journal structure and state transitions (PENDING → OPEN → CLOSED).

**WARNING**: This executor places real orders. Always test on testnet first, with a separate API key, before using on mainnet.

### Common Patterns

**Setting up the executor for a trader's main.py:**

```python
from model_trader.trading.live import HyperliquidExecutor
from model_trader import run_monitor

executor = HyperliquidExecutor(
    journal_path="traders/<name>/executor_trades.json",
    wallet_address=os.environ["HL_WALLET"],
    api_private_key=os.environ["HL_API_KEY"],
    testnet=False,  # Mainnet — be careful
    per_trade_pct=1.0,
)

# In your monitor loop or trading script:
for symbol in symbols:
    result = scanner.evaluate(symbol)
    if result.status == SetupStatus.TAKE:
        trade = executor.execute(result)
        # Result is the journal entry or None

# Periodically reconcile:
executor.check_exits()
```

**Paper vs. live comparison:**

Keep a separate `PaperTrader` instance in the same script and feed it the same `SetupResult` objects. This lets you compare paper and live performance side-by-side.

```python
paper_trader = PaperTrader(...)
executor = HyperliquidExecutor(...)

result = scanner.evaluate(symbol)
if result.status == SetupStatus.TAKE:
    paper_trader.open_trade(result)
    executor.execute(result)
```

## HyperliquidExecutor Details

### Hyperliquid API integration

- **Base SDK**: Uses `hyperliquid-python-sdk` (ETH account signing, info/exchange endpoints).
- **Info API** (read-only, free): Queries open orders, positions, fills, user state for reconciliation.
- **Exchange API** (write, requires API key): Places/cancels orders via signed requests.
- **Testnet vs. mainnet**: Controlled by the `testnet` parameter; points to the corresponding base URL + API endpoint.

### Exchange-side order structure

Entry order (limit, can rest):
```
is_buy: bool based on direction
sz: rounded position size
limit_px: rounded entry price
order_type: {"limit": {"tif": "Gtc"}}  # Good-till-cancel
reduce_only: false
```

SL trigger (reduce-only, auto-closes on touch):
```
is_buy: opposite of entry
sz: rounded position size
limit_px: rounded SL price
order_type: {"trigger": {"isMarket": true, "triggerPx": sl_px, "tpsl": "sl"}}
reduce_only: true
```

TP trigger (similar, with `tpsl: "tp"`).

All three are submitted atomically with `grouping="normalTpsl"` so the exchange ties them together; if the entry fills, the SL/TP orders activate.

### Testnet caveats

- **Builder perps**: Testnet has fewer builder-deployed synth perps than mainnet. Always test with coins that exist on testnet.
- **Liquidity**: Testnet order books are sparse and can have wide spreads. Test fills may not match mainnet fills.
- **API stability**: Testnet API can be reset or experience downtime. Have a circuit breaker to pause trading if reconciliation fails repeatedly.

### Mainnet safety

- **Key management**: Never commit an API private key to git. Use environment variables or a secure key manager (e.g., AWS Secrets Manager, GitHub Secrets).
- **Separate wallet**: Create a dedicated trading wallet with limited funds and trade-only API key. Do NOT use your main wallet's key.
- **Gradual rollout**: Start with very small position sizes (per_trade_pct = 0.1) and increase only after confirming fills and exits work correctly.
- **Monitor errors**: `check_exits()` can raise exceptions (SDK changes, network issues). Wrap it in try/except and log failures prominently.

## Relationship to Paper-Trading Framework

The core `model_trader` framework (described in `docs/architecture.md`) is **paper-trading only**: `PaperTrader`, `run_monitor`, backtest all simulate trades without touching real exchanges. This is intentional — the framework is designed for strategy development, backtesting, and safe iteration.

`HyperliquidExecutor` is a **separate, optional module** that traders use when they are ready to go live. It:

- Does **not** integrate with `PaperTrader` or `run_monitor` directly. Traders must call `executor.execute()` manually or add it to their custom loop, or pass it as `trader` to `PortfolioOrchestrator`.
- Maintains its **own journal** so it doesn't interfere with paper trading.
- Can run **in parallel with paper trading** (useful for comparison) or **instead of it** (live-only).
- Shares position-sizing and close/PnL math with `PaperTrader` via `..journal` (`model_trader.trading.journal`) — only persistence (its own journal) and order placement are exchange-specific.
- Is **not required** to use the framework — traders can keep trading paper indefinitely, or write their own live executor for a different exchange that satisfies the `..journal.Trader` protocol.

### Why are they separate?

1. **Dependency isolation**: Not every trader goes live. Keeping the SDK import lazy (via `__getattr__`) avoids bloating the main package.
2. **Safety**: Accidental confusion between paper and live state is minimized when they have separate journals and explicit control flow.
3. **Modularity**: Other exchanges can be added (e.g., `BinanceExecutor`, `DydxExecutor`) without changing the paper trader or monitor — each new executor implements the same `..journal.Trader` protocol and reuses `..journal`'s sizing/close helpers.

## Dependencies

### Internal
- `..journal` (`model_trader.trading.journal`): `load_journal`, `save_journal`, `size_with_leverage_cap`, `apply_close`, `Trader` protocol.

### External

- `hyperliquid-python-sdk` (live order placement and info queries).
- `eth-account` (ED25519 key handling for Hyperliquid signatures, comes with hyperliquid-python-sdk).
- `requests` (HTTP fallback for info API in case of SDK version mismatch).
- `pathlib`, `json`, `uuid`, `datetime`, `math` (stdlib).

<!-- MANUAL: -->
