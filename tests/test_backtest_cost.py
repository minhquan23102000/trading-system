from model_trader.backtest.runner import _cost_in_r


def test_cost_in_r_basic_long():
    # risk = 1.0, cost_price = 100 * 10/1e4 = 0.1 -> 0.1R
    assert _cost_in_r(100.0, 99.0, 10.0) == 0.1


def test_cost_in_r_basic_short():
    # risk = 1.0, cost_price = 100 * 20/1e4 = 0.2 -> 0.2R
    assert _cost_in_r(100.0, 101.0, 20.0) == 0.2


def test_cost_in_r_tight_stop_dominates():
    # 0.20% stop (mulham floor) vs 10bps cost -> 0.5R per trade
    assert abs(_cost_in_r(100.0, 99.8, 10.0) - 0.5) < 1e-9


def test_cost_in_r_zero_cost():
    assert _cost_in_r(100.0, 99.0, 0.0) == 0.0


def test_cost_in_r_zero_risk():
    assert _cost_in_r(100.0, 100.0, 10.0) == 0.0
