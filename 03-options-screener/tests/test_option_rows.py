import math
from types import SimpleNamespace

from options_screener.option_rows import row_to_contract


def _row(strike=100, bid=1.0, ask=1.2, lastPrice=1.1, volume=50, openInterest=200, impliedVolatility=0.3):
    return SimpleNamespace(
        strike=strike, bid=bid, ask=ask, lastPrice=lastPrice,
        volume=volume, openInterest=openInterest, impliedVolatility=impliedVolatility,
    )


def test_normal_row_converts_correctly():
    c = row_to_contract("TST", "call", _row(), days_to_expiry=30, expiry="2026-01-01")
    assert c.ticker == "TST"
    assert c.option_type == "call"
    assert c.strike == 100
    assert c.bid == 1.0
    assert c.ask == 1.2
    assert c.last_price == 1.1
    assert c.volume == 50
    assert c.open_interest == 200
    assert c.implied_volatility == 0.3
    assert c.days_to_expiry == 30
    assert c.expiry == "2026-01-01"


def test_nan_volume_and_open_interest_default_to_zero_instead_of_crashing():
    row = _row(volume=float("nan"), openInterest=float("nan"))
    c = row_to_contract("TST", "call", row, 30, "2026-01-01")
    assert c is not None
    assert c.volume == 0
    assert c.open_interest == 0


def test_nan_bid_ask_last_price_default_to_zero():
    row = _row(bid=float("nan"), ask=float("nan"), lastPrice=float("nan"))
    c = row_to_contract("TST", "call", row, 30, "2026-01-01")
    assert c is not None
    assert c.bid == 0.0
    assert c.ask == 0.0
    assert c.last_price == 0.0


def test_nan_implied_volatility_skips_the_contract_entirely():
    row = _row(impliedVolatility=float("nan"))
    assert row_to_contract("TST", "call", row, 30, "2026-01-01") is None


def test_zero_implied_volatility_is_not_treated_as_missing():
    row = _row(impliedVolatility=0.0)
    c = row_to_contract("TST", "call", row, 30, "2026-01-01")
    assert c is not None
    assert c.implied_volatility == 0.0


def test_none_values_are_treated_the_same_as_nan():
    row = _row(volume=None, openInterest=None, bid=None, ask=None, lastPrice=None)
    c = row_to_contract("TST", "call", row, 30, "2026-01-01")
    assert c is not None
    assert c.volume == 0
    assert c.open_interest == 0
    assert c.bid == 0.0


def test_none_implied_volatility_skips_the_contract():
    row = _row(impliedVolatility=None)
    assert row_to_contract("TST", "call", row, 30, "2026-01-01") is None
