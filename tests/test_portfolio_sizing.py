from __future__ import annotations

from datetime import datetime, timedelta, timezone

from model_trader.gates import SetupResult, SetupStatus
from model_trader.portfolio.sizing import (
    apply_aggregate_cap,
    apply_correlation_cap,
    compute_weights,
    composite_from_journal,
    daily_dd_breached,
    resolve_same_symbol,
)


def _trade(
    trader_id: str,
    pnl: float | None,
    days_ago: float = 1,
    status: str = "CLOSED",
    risk_amount: float = 100.0,
) -> dict:
    exit_time = None
    if status == "CLOSED":
        exit_time = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "status": status,
        "pnl": pnl,
        "risk_amount": risk_amount,
        "exit_time": exit_time,
        "extras": {"trader_id": trader_id},
    }


def _setup(symbol: str, direction: str, trader_id: str, risk_pct: float = 1.0) -> SetupResult:
    return SetupResult(
        symbol=symbol,
        status=SetupStatus.TAKE,
        direction=direction,
        extras={"trader_id": trader_id, "risk_pct": risk_pct},
    )


def test_composite_basic():
    trades = [_trade("mulham", 50.0) for _ in range(6)] + [
        _trade("mulham", -30.0) for _ in range(4)
    ]

    result = composite_from_journal(trades, "mulham")

    assert result["n"] == 10
    assert result["pf"] == 2.5
    assert result["composite"] > 0
    assert result["composite"] < 100


def test_composite_absent_trader():
    trades = [_trade("mulham", 50.0) for _ in range(6)]

    result = composite_from_journal(trades, "unknown_trader")

    assert result == {"composite": 0.0, "n": 0, "pf": 0.0}


def test_bootstrap_all_below_min():
    composites = {
        "a": {"composite": 5.0, "n": 5, "pf": 1.5},
        "b": {"composite": 3.0, "n": 5, "pf": 1.1},
        "c": {"composite": 1.0, "n": 5, "pf": 0.8},
    }

    weights = compute_weights(composites, base_pct=1.0)

    assert weights == {"a": 1.0, "b": 1.0, "c": 1.0}


def test_tilt_and_clamp():
    composites = {
        "a": {"composite": 11.6, "n": 10, "pf": 2.0},
        "b": {"composite": 8.1, "n": 10, "pf": 1.6},
        "c": {"composite": 6.6, "n": 10, "pf": 1.3},
    }

    weights = compute_weights(composites, base_pct=1.0, min_pct=0.25, max_pct=2.0)

    assert weights["a"] > weights["b"] > weights["c"]
    for w in weights.values():
        assert 0.25 <= w <= 2.0
    assert weights["a"] > 1.0


def test_max_clamp():
    composites = {
        "huge": {"composite": 100.0, "n": 10, "pf": 5.0},
        "b": {"composite": 5.0, "n": 10, "pf": 1.0},
        "c": {"composite": 5.0, "n": 10, "pf": 1.0},
    }

    weights = compute_weights(composites, base_pct=1.0, min_pct=0.25, max_pct=2.0)

    assert weights["huge"] == 2.0
    assert weights["b"] == 0.25
    assert weights["c"] == 0.25


def test_aggregate_cap_scale_down():
    open_trades = [{"status": "OPEN", "symbol": "BTC", "risk_amount": 250.0}]
    decisions = [_setup("ETH", "long", "mulham", risk_pct=1.0)]

    accepted = apply_aggregate_cap(decisions, open_trades, balance=10000, max_portfolio_risk_pct=3.0)

    assert len(accepted) == 1
    assert accepted[0].extras["risk_pct"] == pytest_approx(0.5)


def test_aggregate_cap_drop():
    open_trades = [{"status": "OPEN", "symbol": "BTC", "risk_amount": 300.0}]
    decisions = [_setup("ETH", "long", "mulham", risk_pct=1.0)]

    accepted = apply_aggregate_cap(decisions, open_trades, balance=10000, max_portfolio_risk_pct=3.0)

    assert accepted == []


def test_correlation_cap_blocks_third_crypto():
    open_trades = [
        {"status": "OPEN", "symbol": "BTC", "risk_amount": 100.0},
        {"status": "OPEN", "symbol": "ETH", "risk_amount": 100.0},
    ]
    decisions = [
        _setup("SOL", "long", "mulham"),
        _setup("xyz:GOLD", "long", "mulham"),
    ]

    accepted = apply_correlation_cap(decisions, open_trades)

    assert [d.symbol for d in accepted] == ["xyz:GOLD"]


def test_same_symbol_same_direction():
    composites = {
        "mulham": {"composite": 6.6, "n": 10, "pf": 1.3},
        "tradingnotes": {"composite": 11.6, "n": 10, "pf": 2.0},
    }
    decisions = [
        _setup("BTC", "long", "mulham"),
        _setup("BTC", "long", "tradingnotes"),
    ]

    survivors = resolve_same_symbol(decisions, composites)

    assert len(survivors) == 1
    assert survivors[0].extras["trader_id"] == "tradingnotes"


def test_same_symbol_opposite_direction():
    composites = {
        "mulham": {"composite": 6.6, "n": 10, "pf": 1.3},
        "tradingnotes": {"composite": 11.6, "n": 10, "pf": 2.0},
    }
    decisions = [
        _setup("BTC", "long", "tradingnotes"),
        _setup("BTC", "short", "mulham"),
    ]

    survivors = resolve_same_symbol(decisions, composites)

    assert survivors == []


def test_daily_dd_breached_true():
    starting_balance = 10000.0
    today_iso = datetime.now(timezone.utc).isoformat()
    trades = [
        {"status": "CLOSED", "pnl": -310.0, "exit_time": today_iso},
    ]

    assert daily_dd_breached(trades, starting_balance, dd_pct=3.0) is True


def test_daily_dd_not_breached():
    starting_balance = 10000.0
    today_iso = datetime.now(timezone.utc).isoformat()
    trades = [
        {"status": "CLOSED", "pnl": -290.0, "exit_time": today_iso},
    ]

    assert daily_dd_breached(trades, starting_balance, dd_pct=3.0) is False



def test_composite_seed_used_on_cold_start():
    """Empty journal + seed → composite derived from seed, trader graduates."""
    result = composite_from_journal(
        [], "znasdaq", min_trades=10, seed_pf=5.65, seed_n=21
    )
    import math
    expected = 5.65 * math.log(1 + 21)
    assert abs(result["composite"] - expected) < 0.001
    assert result["n"] == 21        # seed_n returned → trader graduates
    assert result["pf"] == 5.65


def test_composite_seed_ignored_after_graduation():
    """Once min_trades live trades exist, seed is completely ignored."""
    trades = [_trade("znasdaq", 50.0) for _ in range(12)]  # 12 wins, n >= 10
    result = composite_from_journal(
        trades, "znasdaq", min_trades=10, seed_pf=5.65, seed_n=21
    )
    assert result["n"] == 12        # live count, not seed_n
    assert result["pf"] != 5.65    # live PF, not seed


def test_seed_below_min_trades_not_used():
    """seed_n < min_trades → seed ignored, falls back to zero composite."""
    result = composite_from_journal(
        [], "znasdaq", min_trades=10, seed_pf=5.65, seed_n=5
    )
    assert result == {"composite": 0.0, "n": 0, "pf": 0.0}


def test_cold_start_weights_reflect_seed():
    """With seeds, day-1 weights should reflect backtest quality, not equal weight."""
    import math
    composites = {
        "znasdaq": composite_from_journal([], "znasdaq", seed_pf=5.65, seed_n=21),
        "mulham": composite_from_journal([], "mulham", seed_pf=1.80, seed_n=186),
    }
    weights = compute_weights(composites, base_pct=1.0, min_trades=10)
    # znasdaq has higher PF → should get higher weight
    assert weights["znasdaq"] > weights["mulham"]

def pytest_approx(value, rel=1e-6):
    import pytest

    return pytest.approx(value, rel=rel)
