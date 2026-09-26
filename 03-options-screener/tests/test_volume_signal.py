from options_screener.models import OptionContract
from options_screener.volume_signal import unusual_volume_contracts


def _contract(strike, volume, open_interest):
    return OptionContract(
        ticker="TST", option_type="call", strike=strike, expiry="2026-01-01", days_to_expiry=30,
        bid=1.0, ask=1.2, last_price=1.1, volume=volume, open_interest=open_interest, implied_volatility=0.3,
    )


def test_flags_volume_exceeding_open_interest():
    c = _contract(strike=100, volume=500, open_interest=200)
    result = unusual_volume_contracts([c])
    assert len(result) == 1
    assert result[0].volume_to_oi == 2.5
    assert result[0].is_unusual is True


def test_excludes_normal_volume():
    c = _contract(strike=100, volume=150, open_interest=1000)
    assert unusual_volume_contracts([c]) == []


def test_excludes_below_min_volume_even_with_zero_open_interest():
    c = _contract(strike=100, volume=5, open_interest=0)
    assert unusual_volume_contracts([c], min_volume=100) == []


def test_min_volume_does_not_exclude_a_real_signal():
    c = _contract(strike=100, volume=100, open_interest=10)
    result = unusual_volume_contracts([c], min_volume=100)
    assert len(result) == 1


def test_sorted_most_unusual_first():
    mild = _contract(strike=100, volume=120, open_interest=100)  # ratio 1.2
    extreme = _contract(strike=105, volume=1000, open_interest=50)  # ratio 20
    result = unusual_volume_contracts([mild, extreme])
    assert [s.contract.strike for s in result] == [105, 100]


def test_custom_threshold():
    c = _contract(strike=100, volume=150, open_interest=200)  # ratio 0.75
    assert unusual_volume_contracts([c], threshold=1.0) == []
    assert len(unusual_volume_contracts([c], threshold=0.5)) == 1
