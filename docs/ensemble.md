# Ensemble Voting System

Multi-scanner weighted voting engine that replaces the old Claude Agent layer
with deterministic, auditable trade decisions.

## Why ensemble?

Single scanners are fragile. A gate tuned too tightly misses good setups; too
loose and it takes noise. The ensemble runs multiple scanners in parallel, each
implementing the same strategy with different detector weights, then votes.

- **Champion** — highest scoring scanner, gets 50% vote weight. Sets entry/stop/target.
- **Challenger** — alternative scanner implementations, each 25% weight. Vote only.
- **Auto-promotion** — after ≥10 trades, if a challenger's composite score beats the champion, it becomes champion.

## Configuration

Add an `ensemble:` section to `config.yaml`. Each scanner is a **complete
trading strategy** — not a single gate or detector. Multiple scanners can use
the same strategy module with different parameters, or entirely different
strategies.

```yaml
# In config.yaml:
ensemble:
  threshold: 0.5               # min total weight to execute a trade
  db_path: ensemble.db          # SQLite path for trade tracking
  promotion_min_trades: 10      # trades before challenger eligible
  promotion_window_days: 30     # rolling window for promotion cap
  max_promotions_per_window: 1  # prevent promotion flapping
  scanners:
    - id: "ict_default"
      type: "champion"
      weight: 0.5
      active: true
      strategy_module: "scanner"  # import path for scanner class
      params: {}                  # kwargs → Scanner(config, data, **params)
    - id: "ict_loose"
      type: "challenger"
      weight: 0.25
      active: true
      strategy_module: "scanner"  # same strategy, looser gates
      params: {"fvg_tolerance": 2.0}
    - id: "sd_zones"
      type: "challenger"
      weight: 0.25
      active: false               # inactive — skipped on scan cycles
      strategy_module: "scanner_supply_demand"  # different strategy entirely
      params: {}
```
| `params` | dict | `{}` | kwargs passed to `Scanner(config, data_adapter, **params)` |

## Voting Algorithm

```
For each scan cycle:
  1. All active scanners produce SetupResults
  2. TAKE votes are collected, grouped by direction
  3. Direction with highest total weight wins (champion breaks ties)
  4. If total weight ≥ threshold → execute using champion's entry/stop/target
  5. On trade close → update SQLite, check promotion, check degradation
```

### Promotions

After every closed trade, the engine checks if any challenger should be promoted:

```
challenger.composite > champion.composite AND challenger.trade_count ≥ min_trades
→ challenger becomes champion, old champion demoted to challenger
```

**Noise filter**: max 1 promotion per 30-day window. Prevents flapping.

### Degradation Protection

- **Correlation >85%**: if two scanners agree on >85% of setups, they're not independent votes
- **Champion drag**: if ensemble profit factor < champion PF × 0.9 → fallback to champion-only

## Scoring Formula

```
composite = profit_factor × ln(1 + trade_count) × stability_bonus
```

- **profit_factor**: gross_win / abs(gross_loss), clipped to [0, 10]
- **trade_count**: total closed trades in 30-day window
- **stability_bonus**: 1.15 if PF > 1.2 in two consecutive windows, else 1.0

All computed from SQLite with zero new dependencies.

## Running

### Single-scanner mode (backward compatible)

```python
from model_trader import HyperliquidAdapter, PaperTrader, run_monitor
from scanner import Scanner

data = HyperliquidAdapter()
scanner = Scanner(config, data)
paper = PaperTrader(journal_path="trades.json", ...)
run_monitor(scanner, paper)
```

### Ensemble mode

```python
from model_trader import HyperliquidAdapter, PaperTrader, run_monitor
from model_trader.ensemble import load_ensemble_config, EnsembleDB, EnsembleEngine
from scanner import Scanner

data = HyperliquidAdapter()
ensemble_cfg = load_ensemble_config(config)
db = EnsembleDB(ensemble_cfg.db_path)

scanners = [
    Scanner(config, data)  # create one per ensemble scanner def
]
engine = EnsembleEngine(ensemble_cfg, db, scanners)

paper = PaperTrader(journal_path="trades.json", ...)
run_monitor(None, paper, ensemble=engine)
```

### Backtest

```python
python backtest.py
```

Backtest runner auto-detects `ensemble:` in config and runs a separate
backtest per scanner, comparing ensemble PF vs individual scanners.

## Database Schema

SQLite, WAL mode. One table:

```sql
CREATE TABLE trades (
    id TEXT PRIMARY KEY,
    scanner_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    position_size REAL,
    risk_amount REAL,
    rr_ratio REAL,
    status TEXT DEFAULT 'OPEN',
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    exit_price REAL,
    pnl REAL,
    r_multiple REAL,
    outcome TEXT,
    notes TEXT,
    extras TEXT
);
```

## Troubleshooting

- **No trades executing**: check `ensemble.threshold` — if too high (>0.75), most votes fail
- **Champion keeps getting demoted**: reduce `max_promotions_per_window`, or increase `promotion_min_trades`
- **SQLite locked**: only one monitor process at a time (WAL mode handles concurrent reads)
- **Scanners not found**: verify `strategy_module` paths are importable from the trader directory
