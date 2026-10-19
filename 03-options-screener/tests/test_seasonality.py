from datetime import date

import pytest

from options_screener.seasonality import monthly_returns_by_year, seasonal_bias, seasonal_score


def _dates_and_closes():
    dates = []
    closes = []

    # 2021 January: 100 -> 110 (+10%)
    dates += [date(2021, 1, 1), date(2021, 1, 15), date(2021, 1, 29)]
    closes += [100.0, 105.0, 110.0]

    # 2021 February: 110 -> 100 (-9.09%) -- must not leak into January.
    dates += [date(2021, 2, 1), date(2021, 2, 28)]
    closes += [110.0, 100.0]

    # 2022 January: 200 -> 220 (+10%)
    dates += [date(2022, 1, 2), date(2022, 1, 31)]
    closes += [200.0, 220.0]

    # 2023 January: 50 -> 45 (-10%)
    dates += [date(2023, 1, 3), date(2023, 1, 30)]
    closes += [50.0, 45.0]

    # 2024 January: a single data point -- not a real month's return, skipped.
    dates += [date(2024, 1, 15)]
    closes += [75.0]

    return dates, closes


def test_monthly_returns_by_year_matches_hand_calc():
    dates, closes = _dates_and_closes()
    monthly = monthly_returns_by_year(dates, closes)
    assert monthly == {
        (2021, 1): pytest.approx(0.10),
        (2021, 2): pytest.approx(-0.09090909090909091),
        (2022, 1): pytest.approx(0.10),
        (2023, 1): pytest.approx(-0.10),
    }
    # 2024 January has only one close -- not enough to compute a return.
    assert (2024, 1) not in monthly


def test_seasonal_bias_averages_same_month_across_years():
    dates, closes = _dates_and_closes()
    # Three Januaries: +0.10, +0.10, -0.10 -- mean 0.10/3.
    assert seasonal_bias(dates, closes, target_month=1) == pytest.approx((0.10 + 0.10 - 0.10) / 3)


def test_seasonal_bias_none_below_min_years():
    dates, closes = _dates_and_closes()
    # Only one year of February data is present.
    assert seasonal_bias(dates, closes, target_month=2) is None


def test_seasonal_bias_respects_custom_min_years():
    dates, closes = _dates_and_closes()
    # Three Januaries clears a min_years of 2.
    assert seasonal_bias(dates, closes, target_month=1, min_years=2) is not None
    # ...but not a min_years of 4.
    assert seasonal_bias(dates, closes, target_month=1, min_years=4) is None


def test_seasonal_score_centered_at_zero_bias():
    assert seasonal_score(0.0, scale=0.05) == pytest.approx(0.5)


def test_seasonal_score_matches_hand_calc():
    bias = (0.10 + 0.10 - 0.10) / 3
    # 0.5 + bias / (2 * 0.05)
    expected = 0.5 + bias / 0.10
    assert seasonal_score(bias, scale=0.05) == pytest.approx(expected)


def test_seasonal_score_clamped_at_extremes():
    assert seasonal_score(0.5, scale=0.05) == 1.0
    assert seasonal_score(-0.5, scale=0.05) == 0.0


def test_seasonal_score_none_when_bias_is_none():
    assert seasonal_score(None, scale=0.05) is None
