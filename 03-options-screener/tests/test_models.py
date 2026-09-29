from options_screener.models import OptionContract


def _contract(bid, ask, last_price=0.0):
    return OptionContract(
        ticker="TST", option_type="call", strike=100, expiry="2026-01-01", days_to_expiry=30,
        bid=bid, ask=ask, last_price=last_price, volume=10, open_interest=100, implied_volatility=0.3,
    )


def test_mid_price_averages_bid_and_ask():
    c = _contract(bid=1.00, ask=1.20)
    assert c.mid_price == 1.10


def test_mid_price_falls_back_to_last_price_when_no_active_market():
    c = _contract(bid=0, ask=0, last_price=0.85)
    assert c.mid_price == 0.85


def test_total_cost_is_mid_price_times_100():
    # A real user read "$1.65" (the quoted per-share price) as the total
    # cost of one contract, when it actually meant $165 -- this is the
    # number that should have been shown instead.
    c = _contract(bid=1.50, ask=1.80)
    assert c.mid_price == 1.65
    assert c.total_cost == 165.0
