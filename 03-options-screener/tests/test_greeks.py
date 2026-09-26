import pytest

from options_screener.greeks import black_scholes_greeks

# The standard textbook reference case (Hull, "Options, Futures and Other
# Derivatives"): S=100, K=100, 1 year to expiry, r=5%, sigma=20%.
# Call price 10.4506, call delta 0.6368; put price 5.5735, put delta -0.3632.


def test_call_price_and_delta_match_textbook_reference():
    g = black_scholes_greeks(spot=100, strike=100, days_to_expiry=365, implied_volatility=0.2, option_type="call", risk_free_rate=0.05)
    assert g.fair_value == pytest.approx(10.4506, abs=0.001)
    assert g.delta == pytest.approx(0.6368, abs=0.001)


def test_put_price_and_delta_match_textbook_reference():
    g = black_scholes_greeks(spot=100, strike=100, days_to_expiry=365, implied_volatility=0.2, option_type="put", risk_free_rate=0.05)
    assert g.fair_value == pytest.approx(5.5735, abs=0.001)
    assert g.delta == pytest.approx(-0.3632, abs=0.001)


def test_call_delta_is_between_0_and_1():
    g = black_scholes_greeks(spot=50, strike=55, days_to_expiry=30, implied_volatility=0.4, option_type="call")
    assert 0.0 < g.delta < 1.0


def test_put_delta_is_between_minus_1_and_0():
    g = black_scholes_greeks(spot=50, strike=45, days_to_expiry=30, implied_volatility=0.4, option_type="put")
    assert -1.0 < g.delta < 0.0


def test_deep_otm_call_has_low_delta():
    g = black_scholes_greeks(spot=50, strike=100, days_to_expiry=30, implied_volatility=0.5, option_type="call")
    assert g.delta < 0.15


def test_deep_itm_call_has_high_delta():
    g = black_scholes_greeks(spot=100, strike=50, days_to_expiry=30, implied_volatility=0.3, option_type="call")
    assert g.delta > 0.85


def test_gamma_and_vega_are_positive_for_both_call_and_put():
    call = black_scholes_greeks(spot=100, strike=100, days_to_expiry=60, implied_volatility=0.25, option_type="call")
    put = black_scholes_greeks(spot=100, strike=100, days_to_expiry=60, implied_volatility=0.25, option_type="put")
    assert call.gamma > 0
    assert put.gamma > 0
    assert call.vega > 0
    assert put.vega > 0
    # Gamma and vega are the same for a call and put at the same strike/expiry.
    assert call.gamma == pytest.approx(put.gamma)
    assert call.vega == pytest.approx(put.vega)


def test_expiry_day_itm_call_has_delta_one_and_intrinsic_value():
    g = black_scholes_greeks(spot=110, strike=100, days_to_expiry=0, implied_volatility=0.3, option_type="call")
    assert g.delta == 1.0
    assert g.fair_value == pytest.approx(10.0)
    assert g.gamma == 0.0
    assert g.theta == 0.0
    assert g.vega == 0.0


def test_expiry_day_otm_put_has_delta_zero_and_zero_value():
    g = black_scholes_greeks(spot=110, strike=100, days_to_expiry=0, implied_volatility=0.3, option_type="put")
    assert g.delta == 0.0
    assert g.fair_value == 0.0


def test_zero_implied_volatility_falls_back_to_intrinsic_value():
    g = black_scholes_greeks(spot=110, strike=100, days_to_expiry=10, implied_volatility=0.0, option_type="call")
    assert g.fair_value == pytest.approx(10.0)


def test_invalid_option_type_raises():
    with pytest.raises(ValueError):
        black_scholes_greeks(spot=100, strike=100, days_to_expiry=30, implied_volatility=0.2, option_type="straddle")
