# Portfolio Layer

## Purpose

The portfolio layer runs three independent traders — `tradingnotes`, `znasdaq`, and `mulham` — against a single shared equity pool. Each trader produces its own `SetupResult` signals; the orchestrator weighs them by composite score, applies four caps, and routes approved trades through one shared executor (paper or live). The `tradingnotes` and `mulham` traders both trade BTC, ETH, and SOL, creating a partial basket overlap in the CRYPTO correlation group. Because the CRYPTO cap limits concurrent crypto positions to two, those three shared symbols compete for slots across both traders at scan time.

---

## Architecture

```
PortfolioOrchestrator  (src/model_trader/portfolio/orchestrator.py)
  ├── scanners: dict[trader_id, ScannerBase]
  │     tradingnotes  (BTC, ETH, SOL, BNB)
  │     znasdaq       (xyz:GOLD, xyz:SP500)
  │     mulham        (BTC, ETH, SOL, AVAX)
  ├── shared PaperTrader  or  HyperliquidExecutor
  │     one journal:  traders/portfolio_trades.json
  └── sizing logic   (src/model_trader/portfolio/sizing.py, pure functions)
```

`ensemble/` is **not** involved here. The ensemble layer solves a different problem: voting across model variants for a single-asset signal. The portfolio layer runs fully independent multi-asset traders.

---

## Composite Scoring

Computed entirely from the shared JSON journal by `composite_from_journal()` in `sizing.py`. No SQLite.

```
composite = PF × ln(1 + n) × stability
```

- **PF** — profit factor of closed trades in the rolling `window_days` (default 90) window, clipped to `[0.0, 10.0]`.
- **n** — count of closed trades for the trader within that window.
- **stability** — `1.15` if both the current window PF and the prior window PF exceed `1.2`; otherwise `1.0`.

**Bootstrap**: a trader with fewer than `min_trades` closed trades (default 10) is not yet graduated. Ungraduated traders receive the mean composite of graduated traders as their effective score. If no trader has graduated, all get `base_risk_pct` equally.

---

## Sizing

Computed by `compute_weights()` in `sizing.py`:

```
risk_pct_i = clamp(base × eff_i / mean(eff),  0.25%,  2.0%)
```

- `base` — default `1.0%` of account balance per trade.
- `eff_i` — effective composite for trader `i` (own composite if graduated, mean otherwise).
- `mean(eff)` — mean effective composite across all traders.
- Clamp range: floor `0.25%`, ceiling `2.0%`.

**Max portfolio open risk**: `3.0%` total across all concurrent open positions.

---

## Caps

Applied in order inside `scan_cycle()` on each set of candidate `TAKE` signals:

1. **Aggregate open-risk cap** (`apply_aggregate_cap`)  
   Total open + new risk must not exceed `3.0%` of balance. Candidates are sorted by composite descending; any trade that would push total risk over the cap is dropped.

2. **Correlation-group cap** (`apply_correlation_cap`)  
   Maximum concurrent open positions per group:
   - `CRYPTO` → 2
   - `METALS` → 1
   - `INDEX`  → 1
   Candidates exceeding the cap for their group are dropped (sorted by composite descending; best kept first).

3. **Same-symbol conflict** (`resolve_same_symbol`)  
   If two traders both signal the same symbol:
   - Same direction → the higher-composite trader's signal wins.
   - Opposite directions → both are dropped.

4. **Daily drawdown stop** (`daily_dd_breached`)  
   If today's realized PnL ≤ −3.0% of `starting_balance`, no new entries are accepted for the rest of the day.

---

## Correlation Groups

| Symbol | Group |
|---|---|
| BTC, ETH, SOL, BNB, AVAX | CRYPTO |
| xyz:GOLD, xyz:SILVER | METALS |
| xyz:SP500, xyz:NVDA | INDEX |

Symbols not in any group are assigned `"OTHER"` by `group_for()` with no cap applied.

**Overlap note**: `mulham` trades BTC/ETH/SOL/AVAX and `tradingnotes` trades BTC/ETH/SOL/BNB. All six symbols fall in CRYPTO. With the cap at 2, at most two CRYPTO positions can be open at once regardless of how many scanners trigger — the highest-composite signals win the slots.

---

## Running

```bash
# Paper trading (default: paper_trading: true in each trader's config)
uv run python traders/portfolio_run.py

# Walk-forward backtest proof
uv run python traders/portfolio_backtest.py
```

For live mode: set `paper_trading: false` in `traders/tradingnotes/config.yaml` (or whichever traders should go live), then export:

```bash
export HL_WALLET=0x...          # main wallet address
export HL_PRIVATE_KEY=0x...     # API wallet private key (trade permission only)
```

---

## Paper → Live Cutover

Flip `paper_trading: false` in the relevant trader config. The orchestrator, scanners, and sizing functions are unchanged — they operate on `SetupResult` objects and the JSON journal regardless of executor. `HyperliquidExecutor` (`src/model_trader/trading/live/hyperliquid.py`) accepts the same `SetupResult` interface as `PaperTrader`. On entry, it places exchange-side SL and TP trigger orders so exits fire on Hyperliquid even if the bot goes offline. The journal gains exchange-specific fields (`entry_oid`, `sl_oid`, `tp_oid`, `fill_time`) but remains structurally compatible with the composite scoring logic.

---

## Limitations

- `HyperliquidExecutor.get_balance()` queries the default Hyperliquid dex. GOLD and SP500 margin lives on the `xyz` builder-deployed dex and is **not** included in the balance used for sizing calculations.
- `mulham` (BTC/ETH/SOL/AVAX) and `tradingnotes` (BTC/ETH/SOL/BNB) share three symbols. The CRYPTO cap reduces but does not eliminate correlated drawdown — two concurrent CRYPTO positions can still be from the same basket.
- `portfolio_backtest.py` runs each trader independently with `run_backtest()`. It does not jointly simulate same-symbol collision resolution or the aggregate cap across traders; correlation between equity curves is reported post-hoc, not enforced during simulation.
