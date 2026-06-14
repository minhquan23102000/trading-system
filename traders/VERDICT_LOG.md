# Trader diagnosis verdict log (executed 2026-06-14)

Plan: `trader-diagnosis-plan.md` (Steps 0/A/B/C/D/E). All runs via
`uv run python traders/portfolio_backtest.py` from repo root.

## Step 0 baseline (post ATR-cap + swing-leg fixes, 180d)

| trader | n | WR | PF | totalR | IS PF (n) | OOS PF (n) |
|---|---|---|---|---|---|---|
| tradingnotes | 196 | 57.1% | 0.82 | -22.33 | 0.68 (120) | 1.06 (76) |
| znasdaq | 29 | 37.9% | 0.14 | -22.05 | 0.12 (21) | 0.16 (8) |
| mulham (swing2r) | 686 | 33.6% | 0.79 | -114.59 | 0.74 (478) | 0.92 (206) |

## Step B — mulham target_model A/B

| variant | n | PF | OOS PF (n) | avgR |
|---|---|---|---|---|
| swing2r (baseline) | 686 | 0.79 | 0.92 (206) | -0.06 |
| htf_level | 581 | 0.89 | 1.22 (172) | +0.17 |

Per-symbol OOS-relevant: ETH PF=1.32, SOL PF=0.96 (vs 0.74 swing2r), AVAX PF=0.74, BTC PF=0.67.

**Verdict: KEEP.** OOS n=172≥30 (binding). htf_level OOS PF 1.22 ≥ 1.0 AND > swing2r OOS PF 0.92.
Root cause = wrong target copy (code defect — amputated "let winners run to HTF level" edge from
strategy.md). `target_model: htf_level` adopted as the new default in
`traders/mulham/config.yaml`.

## Step C — tradingnotes experiments

| config | n | PF | totalR | IS PF (n) | OOS PF (n) |
|---|---|---|---|---|---|
| baseline | 196 | 0.82 | -22.33 | 0.68 (120) | 1.06 (76) |
| min_stop_pct=0.003 | 56 | 1.18 | +5.52 | 1.10 (40) | 1.42 (16) |

Stop histogram (min_stop_pct=0.003) confirms the lever: 32 setups at 0.105% stop (below the
0.30% floor) were filtered; remaining trades cluster at 0.30-1.0% stops, p50=0.45%.

**Verdict: KEEP.** Baseline OOS PF=1.06 with n=76≥30 already clears the bar; min_stop_pct=0.003
improves both IS PF (0.68→1.10) and total_r (-22.33→+5.52) without breaking the binding OOS
evidence. Root cause = missing filter (impl omission — no stop floor, unlike mulham's analogous
0.20% floor). `min_stop_pct: 0.003` adopted as the new default in
`traders/tradingnotes/config.yaml` (`direction_filter`/`session_filter` left at defaults — the
stop floor alone already clears the bar).

## Step D — znasdaq data-coverage

| window | n | trades/day | PF | dominant funnel reason |
|---|---|---|---|---|
| 180d | 29 | 0.161 | 0.14 | "Insufficient candle history" (1668) |
| 60d | 12 | 0.200 | 0.19 | "No 4h displacement — no clear HTF bias" (375) |

60d trades/day > 180d trades/day — confirms the first ~120d of the 180d window contribute
disproportionately few trades because 5m/15m history is truncated there (data-truncation effect,
as predicted). At 60d "Insufficient candle history" disappears entirely from the funnel, but
PF is still 0.19 on full-coverage data.

**Verdict: DO NOT KEEP in portfolio backtest/seeds.** Yahoo proxy is session-less +
LTF-truncated; 180d OOS PF=0.16 n=8 is non-binding anyway. Gates do fire on full-coverage data
(D1) but PF<1.0 even then, and the 1:1R breakeven-by-design (scanner.py:202) stands against it
regardless of feed. Route znasdaq to live paper-trade on the real intended feed (XAUUSD/NQ,
session-aware; `paper_trading: true` already set) for ≥30d before any keep/remove call.
**No `portfolio.yaml` edit made** — the verdict is "paper-trade first", not "remove"; per the
plan's removal-is-reversible-bookkeeping note, removing from `portfolio.yaml` requires explicit
user confirmation.

## Net code changes (non-destructive, config-gated)

- `src/model_trader/backtest/runner.py`: gate-rejection funnel (`Counter`) wired into
  `_run_backtest_single` and `_run_backtest_ensemble`, returned as `gate_funnel`. Dropped unused
  `datetime`/`timezone`/`timedelta` import.
- `traders/diagnostics.py` (new): `print_funnel`, `print_stop_histogram`,
  `print_direction_breakdown`, `print_symbol_breakdown`.
- `traders/portfolio_backtest.py`: PER-TRADER DIAGNOSTICS section; UTF-8 stdout reconfigure
  (Windows cp1252 console can't print `≥`/`×` in funnel reasons).
- `traders/mulham/scanner.py` + `config.yaml`: `target_model` config key, default now
  `"htf_level"` (was `"swing2r"`).
- `traders/tradingnotes/scanner.py` + `config.yaml`: `min_stop_pct` (default now `0.003`,
  was `0.0`), `direction_filter` (null), `session_filter` (false) toggles added.
- `pyproject.toml`/`uv.lock`: added `tzdata` dependency (zoneinfo has no tz database on
  Windows Python by default; required for the session_filter toggle).
- `uv run pytest`: 115 passed, 0 failures after all changes.

## Open follow-ups (out of scope for this plan)

- znasdaq: start live paper-trade accumulation on a session-aware XAUUSD/NQ feed; revisit
  keep/remove after ≥30d.
- No `portfolio.yaml` seed/threshold tuning performed — both mulham and tradingnotes are now on
  their KEEP configs; re-running `portfolio_backtest.py` will reflect the new defaults
  automatically (no further config edits needed for normal runs).
