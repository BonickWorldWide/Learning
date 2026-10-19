import pytest

from options_screener.models import OptionContract
from options_screener.volume_signal import average_volume, relative_volume, unusual_volume_contracts


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
    c = _contract(strike=100, volume=100, open_interest=60)
    result = unusual_volume_contracts([c], min_volume=100)
    assert len(result) == 1


def test_excludes_below_min_open_interest_even_with_a_perfect_ratio():
    # volume=100/open_interest=100 clears min_volume and hits the ratio
    # threshold exactly, but a hundred contracts total open is itself a
    # sign almost nobody trades this strike -- one order, not conviction.
    c = _contract(strike=100, volume=100, open_interest=40)
    assert unusual_volume_contracts([c], min_open_interest=50) == []


def test_sorted_most_unusual_first():
    mild = _contract(strike=100, volume=120, open_interest=100)  # ratio 1.2
    extreme = _contract(strike=105, volume=1000, open_interest=50)  # ratio 20
    result = unusual_volume_contracts([mild, extreme])
    assert [s.contract.strike for s in result] == [105, 100]


def test_custom_threshold():
    c = _contract(strike=100, volume=150, open_interest=200)  # ratio 0.75
    assert unusual_volume_contracts([c], threshold=1.0) == []
    assert len(unusual_volume_contracts([c], threshold=0.5)) == 1


def test_relative_volume_matches_hand_calc():
    # 20 baseline days at 1,000,000, then 5 recent days at 3,000,000 ->
    # 3,000,000 / 1,000,000 = 3.0.
    volumes = [1_000_000] * 20 + [3_000_000] * 5
    assert relative_volume(volumes) == pytest.approx(3.0)


def test_relative_volume_of_one_means_trading_normally():
    volumes = [2_000_000] * 25
    assert relative_volume(volumes) == pytest.approx(1.0)


def test_relative_volume_none_with_too_little_history():
    volumes = [1_000_000] * 24  # one short of the default 5 + 20
    assert relative_volume(volumes) is None


def test_relative_volume_none_with_zero_baseline_volume():
    volumes = [0] * 20 + [1_000_000] * 5
    assert relative_volume(volumes) is None


def test_relative_volume_custom_windows():
    volumes = [500_000] * 10 + [1_500_000] * 3
    assert relative_volume(volumes, recent=3, baseline=10) == pytest.approx(3.0)


def test_average_volume_matches_hand_calc():
    # 15 days at 1,000,000 then 5 at 2,000,000 -- (15*1M + 5*2M) / 20.
    volumes = [1_000_000] * 15 + [2_000_000] * 5
    assert average_volume(volumes) == pytest.approx(1_250_000.0)


def test_average_volume_uses_whatever_history_is_available():
    # Fewer than `window` days -- averages what's there rather than None.
    assert average_volume([1_000_000, 3_000_000], window=20) == pytest.approx(2_000_000.0)


def test_average_volume_respects_window():
    # A volume spike far outside the trailing window shouldn't count.
    volumes = [10_000_000] * 5 + [1_000_000] * 20
    assert average_volume(volumes, window=20) == pytest.approx(1_000_000.0)


def test_average_volume_none_for_empty_input():
    assert average_volume([]) is None
