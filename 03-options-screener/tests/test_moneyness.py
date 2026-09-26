from options_screener.models import OptionContract
from options_screener.moneyness import find_cheap_near_money, moneyness_pct


def _contract(strike, bid, ask, option_type="call", iv=0.3, dte=30):
    return OptionContract(
        ticker="TST", option_type=option_type, strike=strike, expiry="2026-01-01",
        days_to_expiry=dte, bid=bid, ask=ask, last_price=(bid + ask) / 2 if bid and ask else 0,
        volume=100, open_interest=500, implied_volatility=iv,
    )


def test_moneyness_pct_positive_when_strike_above_spot():
    c = _contract(strike=110, bid=1, ask=1.2)
    assert moneyness_pct(c, spot=100) == 0.10


def test_moneyness_pct_negative_when_strike_below_spot():
    c = _contract(strike=90, bid=1, ask=1.2)
    assert moneyness_pct(c, spot=100) == -0.10


def test_excludes_contracts_outside_the_band():
    far = _contract(strike=130, bid=0.50, ask=0.60)  # 30% OTM, way outside a 5% band
    near = _contract(strike=102, bid=0.50, ask=0.60)
    result = find_cheap_near_money([far, near], spot=100, band_pct=0.05)
    assert [cand.contract for cand in result] == [near]


def test_excludes_contracts_above_max_premium():
    cheap = _contract(strike=101, bid=1.00, ask=1.20)
    expensive = _contract(strike=99, bid=5.00, ask=5.20)
    result = find_cheap_near_money([cheap, expensive], spot=100, band_pct=0.05, max_premium=2.00)
    assert [cand.contract for cand in result] == [cheap]


def test_sorted_cheapest_first():
    pricier = _contract(strike=101, bid=1.50, ask=1.70)
    cheaper = _contract(strike=99, bid=0.40, ask=0.60)
    result = find_cheap_near_money([pricier, cheaper], spot=100, band_pct=0.05)
    assert [cand.contract.strike for cand in result] == [99, 101]


def test_zero_premium_contract_is_excluded():
    dead = _contract(strike=100, bid=0, ask=0)
    result = find_cheap_near_money([dead], spot=100)
    assert result == []


def test_each_candidate_carries_its_own_greeks():
    c = _contract(strike=100, bid=1.00, ask=1.20, option_type="call")
    result = find_cheap_near_money([c], spot=100, band_pct=0.05)
    assert len(result) == 1
    assert 0.0 < result[0].greeks.delta < 1.0
