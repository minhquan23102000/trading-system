"""Functional tests for the consolidated `model_trader.trading` package.

Covers the shared journal primitives (`journal.py`), `PaperTrader`, the
duplicate/invalidated-level filters, metrics, and the `Trader` protocol —
none of this had test coverage before the paper_trader/executor -> trading
restructure.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from model_trader.gates import SetupResult, SetupStatus
from model_trader.trading import (
    PaperTrader,
    Trader,
    apply_close,
    calculate_metrics,
    is_duplicate_setup,
    is_invalidated_level,
    load_journal,
    save_journal,
    size_with_leverage_cap,
)


# ───────────────────────── journal primitives ─────────────────────────


def test_size_with_leverage_cap_no_binding():
    # 1% of 100k risk, $50 stop distance -> size 20, risk unchanged.
    size, risk = size_with_leverage_cap(
        balance=100_000, risk_pct=1.0, entry=1000, stop_dist=50, max_leverage=25
    )
    assert size == pytest.approx(20.0)
    assert risk == pytest.approx(1_000.0)
    # Sanity: notional well under the leverage cap.
    assert size * 1000 < 100_000 * 25


def test_size_with_leverage_cap_binds_and_shrinks_risk():
    # Large entry price + tiny stop distance -> notional blows past 25x leverage.
    balance, entry, stop_dist, max_leverage = 100_000, 100_000, 1, 25
    size, risk = size_with_leverage_cap(balance, 1.0, entry, stop_dist, max_leverage)

    max_notional = balance * max_leverage
    assert size * entry == pytest.approx(max_notional)
    # risk = size * stop_dist, shrunk in lockstep with size
    assert risk == pytest.approx(size * stop_dist)
    # Without the cap, risk would have been balance * 1% = 1000.
    assert risk < 1000


def test_apply_close_long_win_and_r_multiple():
    trade = {
        "direction": "long",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "position_size": 10.0,
    }
    apply_close(trade, "TP_HIT", 110.0)

    assert trade["status"] == "CLOSED"
    assert trade["pnl"] == pytest.approx(100.0)  # (110-100)*10
    assert trade["r_multiple"] == pytest.approx(2.0)  # 100 / (10*5)
    assert trade["outcome"] == "WIN"
    assert trade["notes"] == "TP_HIT"
    assert trade["exit_price"] == 110.0


def test_apply_close_short_loss():
    trade = {
        "direction": "short",
        "entry_price": 100.0,
        "stop_loss": 105.0,
        "position_size": 4.0,
    }
    apply_close(trade, "SL_HIT", 105.0)

    assert trade["pnl"] == pytest.approx(-20.0)  # (100-105)*4
    assert trade["outcome"] == "LOSS"
    assert trade["r_multiple"] == pytest.approx(-1.0)  # -20 / (4*5)


def test_apply_close_breakeven():
    trade = {
        "direction": "long",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "position_size": 1.0,
    }
    apply_close(trade, "MANUAL", 100.0)
    assert trade["pnl"] == 0
    assert trade["outcome"] == "BE"


def test_apply_close_zero_stop_distance_gives_zero_r():
    trade = {
        "direction": "long",
        "entry_price": 100.0,
        "stop_loss": 100.0,
        "position_size": 1.0,
    }
    apply_close(trade, "MANUAL", 105.0)
    assert trade["r_multiple"] == 0


def test_load_save_journal_roundtrip(tmp_path):
    path = tmp_path / "nested" / "journal.json"
    assert load_journal(path) == []  # missing file -> []

    trades = [{"id": "abc", "status": "OPEN"}]
    save_journal(path, trades)
    assert path.exists()
    assert load_journal(path) == trades


# ───────────────────────── PaperTrader ─────────────────────────


def _take_setup(**overrides) -> SetupResult:
    defaults = dict(
        symbol="BTC",
        status=SetupStatus.TAKE,
        direction="long",
        entry=100.0,
        stop=95.0,
        target=110.0,
    )
    defaults.update(overrides)
    return SetupResult(**defaults)


class FakeDataAdapter:
    """Returns one canned 1m candle per symbol; mutate `.candle` between calls."""

    def __init__(self, candle: dict):
        self.candle = candle
        self.calls = 0

    def fetch_candles(self, symbol, timeframe, limit=1):
        self.calls += 1
        return [self.candle]


@pytest.fixture
def journal_path(tmp_path):
    return tmp_path / "trades.json"


def test_execute_rejects_non_take(journal_path):
    trader = PaperTrader(journal_path)
    setup = _take_setup(status=SetupStatus.SKIP)
    assert trader.execute(setup) is None
    assert trader.get_all_trades() == []


def test_execute_rejects_missing_prices(journal_path):
    trader = PaperTrader(journal_path)
    assert trader.execute(_take_setup(entry=None)) is None
    assert trader.execute(_take_setup(stop=None)) is None
    assert trader.execute(_take_setup(target=None)) is None


def test_execute_rejects_zero_stop_distance(journal_path):
    trader = PaperTrader(journal_path)
    assert trader.execute(_take_setup(entry=100.0, stop=100.0)) is None


def test_execute_opens_and_persists_trade(journal_path):
    trader = PaperTrader(journal_path, starting_balance=100_000, per_trade_pct=1.0, max_leverage=25)
    trade = trader.execute(_take_setup())

    assert trade is not None
    assert trade["status"] == "OPEN"
    assert trade["rr_ratio"] == pytest.approx(2.0)  # (110-100)/(100-95)
    # 1% of 100k / stop_dist(5) = 200 units
    assert trade["position_size"] == pytest.approx(200.0)
    assert trade["risk_amount"] == pytest.approx(1_000.0)

    persisted = json.loads(journal_path.read_text())
    assert len(persisted) == 1
    assert persisted[0]["id"] == trade["id"]
    assert trader.get_open_trades() == persisted


def test_execute_uses_extras_risk_pct_override(journal_path):
    trader = PaperTrader(journal_path, starting_balance=100_000, per_trade_pct=1.0)
    setup = _take_setup(extras={"risk_pct": 2.0})
    trade = trader.execute(setup)
    assert trade["risk_amount"] == pytest.approx(2_000.0)
    assert trade["position_size"] == pytest.approx(400.0)


def test_check_exits_no_data_adapter_returns_empty(journal_path):
    trader = PaperTrader(journal_path)
    trader.execute(_take_setup())
    assert trader.check_exits() == []
    # Trade remains open since there's nothing to check against.
    assert trader.get_open_trades()[0]["status"] == "OPEN"


def test_check_exits_long_sl_hit(journal_path):
    data = FakeDataAdapter({"high": 102, "low": 90, "close": 91})  # low <= sl(95)
    trader = PaperTrader(journal_path, data_adapter=data)
    trader.execute(_take_setup())  # long, entry 100, sl 95, tp 110

    closed = trader.check_exits()
    assert len(closed) == 1
    assert closed[0]["notes"] == "SL_HIT"
    assert closed[0]["status"] == "CLOSED"
    assert closed[0]["outcome"] == "LOSS"
    assert trader.get_open_trades() == []


def test_check_exits_long_tp_hit(journal_path):
    data = FakeDataAdapter({"high": 111, "low": 99, "close": 105})  # high >= tp(110)
    trader = PaperTrader(journal_path, data_adapter=data)
    trader.execute(_take_setup())

    closed = trader.check_exits()
    assert len(closed) == 1
    assert closed[0]["notes"] == "TP_HIT"
    assert closed[0]["outcome"] == "WIN"


def test_check_exits_sl_priority_over_tp_for_long(journal_path):
    # Both SL and TP within this candle's range -> SL takes priority.
    data = FakeDataAdapter({"high": 111, "low": 90, "close": 100})
    trader = PaperTrader(journal_path, data_adapter=data)
    trader.execute(_take_setup())

    closed = trader.check_exits()
    assert closed[0]["notes"] == "SL_HIT"


def test_check_exits_short_sl_and_tp(journal_path):
    # Short: entry 100, sl 105, tp 90 (target below entry).
    setup = _take_setup(direction="short", entry=100.0, stop=105.0, target=90.0)

    # TP hit: low <= tp(90)
    data = FakeDataAdapter({"high": 101, "low": 89, "close": 90})
    trader = PaperTrader(journal_path, data_adapter=data)
    trader.execute(setup)
    closed = trader.check_exits()
    assert closed[0]["notes"] == "TP_HIT"
    assert closed[0]["outcome"] == "WIN"


def test_check_exits_short_sl_hit(journal_path):
    setup = _take_setup(direction="short", entry=100.0, stop=105.0, target=90.0)
    data = FakeDataAdapter({"high": 106, "low": 95, "close": 100})  # high >= sl(105)
    trader = PaperTrader(journal_path, data_adapter=data)
    trader.execute(setup)
    closed = trader.check_exits()
    assert closed[0]["notes"] == "SL_HIT"
    assert closed[0]["outcome"] == "LOSS"


def test_balance_compounds_realized_pnl_only(journal_path):
    data = FakeDataAdapter({"high": 111, "low": 99, "close": 105})  # TP hit
    trader = PaperTrader(journal_path, starting_balance=100_000, data_adapter=data)

    trader.execute(_take_setup())  # opens; balance still 100k while OPEN
    assert trader.get_balance() == pytest.approx(100_000)

    trader.check_exits()  # closes with TP -> pnl = (110-100)*200 = 2000
    assert trader.get_balance() == pytest.approx(102_000)


# ───────────────────────── filters ─────────────────────────


def _write_trades(path, trades):
    save_journal(path, trades)


def test_is_duplicate_setup_true_within_tolerance_and_lookback(journal_path):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _write_trades(journal_path, [{
        "symbol": "BTC", "status": "CLOSED", "exit_time": recent,
        "entry_price": 100.0, "stop_loss": 95.0, "take_profit": 110.0,
    }])
    # Within 0.02% tolerance of the closed trade's prices.
    assert is_duplicate_setup(journal_path, "BTC", 100.01, 95.0, 110.0) is True


def test_is_duplicate_setup_false_outside_lookback(journal_path):
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    _write_trades(journal_path, [{
        "symbol": "BTC", "status": "CLOSED", "exit_time": old,
        "entry_price": 100.0, "stop_loss": 95.0, "take_profit": 110.0,
    }])
    assert is_duplicate_setup(journal_path, "BTC", 100.0, 95.0, 110.0, lookback_minutes=15) is False


def test_is_duplicate_setup_false_different_symbol_or_prices(journal_path):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    _write_trades(journal_path, [{
        "symbol": "BTC", "status": "CLOSED", "exit_time": recent,
        "entry_price": 100.0, "stop_loss": 95.0, "take_profit": 110.0,
    }])
    assert is_duplicate_setup(journal_path, "ETH", 100.0, 95.0, 110.0) is False
    assert is_duplicate_setup(journal_path, "BTC", 120.0, 95.0, 110.0) is False


def test_is_invalidated_level_true_when_price_hasnt_moved_away(journal_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    # Long trade stopped out at 95.
    _write_trades(journal_path, [{
        "symbol": "BTC", "direction": "long", "notes": "SL_HIT",
        "exit_time": recent, "stop_loss": 95.0,
    }])
    # New long proposes the same stop, current price barely above blown level.
    assert is_invalidated_level(
        journal_path, "BTC", "long", stop=95.0, current_price=95.1,
        required_distance_pct=0.5,
    ) is True


def test_is_invalidated_level_false_when_price_moved_away(journal_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _write_trades(journal_path, [{
        "symbol": "BTC", "direction": "long", "notes": "SL_HIT",
        "exit_time": recent, "stop_loss": 95.0,
    }])
    # required_distance = 95 * 0.5% = 0.475; price moved +1 -> not invalidated.
    assert is_invalidated_level(
        journal_path, "BTC", "long", stop=95.0, current_price=96.0,
        required_distance_pct=0.5,
    ) is False


def test_is_invalidated_level_false_when_too_old(journal_path):
    old = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    _write_trades(journal_path, [{
        "symbol": "BTC", "direction": "long", "notes": "SL_HIT",
        "exit_time": old, "stop_loss": 95.0,
    }])
    assert is_invalidated_level(
        journal_path, "BTC", "long", stop=95.0, current_price=95.1,
        max_age_hours=6,
    ) is False


# ───────────────────────── metrics ─────────────────────────


def test_calculate_metrics_empty_journal(journal_path):
    assert calculate_metrics(journal_path) == {
        "total_trades": 0, "wins": 0, "losses": 0,
        "win_rate": 0, "avg_rr": 0, "profit_factor": 0,
        "total_pnl": 0, "max_drawdown": 0,
    }


def test_calculate_metrics_missing_file(tmp_path):
    assert calculate_metrics(tmp_path / "nope.json")["total_trades"] == 0


def test_calculate_metrics_mixed_trades(journal_path):
    trades = [
        {"status": "CLOSED", "outcome": "WIN", "pnl": 200, "r_multiple": 2.0},
        {"status": "CLOSED", "outcome": "LOSS", "pnl": -100, "r_multiple": -1.0},
        {"status": "OPEN"},  # ignored
    ]
    _write_trades(journal_path, trades)
    m = calculate_metrics(journal_path)

    assert m["total_trades"] == 2
    assert m["wins"] == 1
    assert m["losses"] == 1
    assert m["win_rate"] == 50.0
    assert m["avg_rr"] == pytest.approx(0.5)
    assert m["profit_factor"] == pytest.approx(2.0)  # 200 / 100
    assert m["total_pnl"] == pytest.approx(100)


def test_calculate_metrics_profit_factor_inf_when_no_losses(journal_path):
    _write_trades(journal_path, [
        {"status": "CLOSED", "outcome": "WIN", "pnl": 50, "r_multiple": 1.0},
    ])
    m = calculate_metrics(journal_path)
    assert m["profit_factor"] == float("inf")


# ───────────────────────── Trader protocol ─────────────────────────


def test_paper_trader_satisfies_trader_protocol(journal_path):
    trader = PaperTrader(journal_path)
    assert isinstance(trader, Trader)


def test_hyperliquid_executor_satisfies_trader_protocol():
    from pathlib import Path

    from model_trader.trading.live import HyperliquidExecutor

    # Avoid network calls in __init__: check structural conformance on a
    # bare instance (Protocol isinstance only inspects attribute presence).
    # journal_path is normally set in __init__; set it here so the
    # data-attribute check in the runtime_checkable Protocol passes.
    bare = HyperliquidExecutor.__new__(HyperliquidExecutor)
    bare.journal_path = Path("unused.json")
    assert isinstance(bare, Trader)


def test_trading_package_exports():
    import model_trader.trading as trading

    for name in (
        "PaperTrader", "Trade", "Trader", "TradeRecord",
        "is_duplicate_setup", "is_invalidated_level", "calculate_metrics",
        "apply_close", "load_journal", "save_journal", "size_with_leverage_cap",
    ):
        assert hasattr(trading, name), f"missing export: {name}"


def test_top_level_package_exports_paper_trader_and_trader():
    import model_trader as mt

    assert mt.PaperTrader is not None
    assert mt.Trader is not None
    assert "PaperTrader" in mt.__all__
    assert "Trader" in mt.__all__
    assert mt.TradeRecord is not None
    assert "TradeRecord" in mt.__all__
