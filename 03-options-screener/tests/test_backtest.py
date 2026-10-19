from datetime import date, timedelta

import pytest

from options_screener.backtest import (
    MIN_HISTORY_FOR_SCORE,
    BacktestResult,
    evaluate_predictive_power,
    forward_return,
    historical_composite_score,
    walk_history,
)


def test_forward_return_matches_hand_calc():
    closes = [100.0, 105.0, 110.0, 90.0]
    assert forward_return(closes, 0, 2) == pytest.approx(0.10)  # 100 -> 110
    assert forward_return(closes, 1, 2) == pytest.approx((90.0 - 105.0) / 105.0)


def test_forward_return_none_when_horizon_runs_past_the_end():
    closes = [100.0, 105.0, 110.0, 90.0]
    assert forward_return(closes, 2, 2) is None  # target index 4 doesn't exist


def test_forward_return_none_for_a_non_positive_starting_close():
    assert forward_return([0.0, 100.0, 110.0], 0, 1) is None


def test_historical_composite_score_is_momentum_alone_when_nothing_else_present():
    assert historical_composite_score(0.8) == pytest.approx(0.8)


def test_historical_composite_score_averages_whichever_are_present():
    assert historical_composite_score(0.8, movement=0.4) == pytest.approx(0.6)


def test_historical_composite_score_matches_hand_calc_with_all_five():
    score = historical_composite_score(0.8, movement=0.4, jump=0.2, market_trend=1.0, seasonal=0.6)
    assert score == pytest.approx((0.8 + 0.4 + 0.2 + 1.0 + 0.6) / 5)


def test_evaluate_predictive_power_matches_hand_calc():
    # success_threshold 0.10, score_threshold 0.5.
    # Baseline: 3 of 6 pairs have forward_return >= 0.10 -> 0.5.
    # Signal (score >= 0.5): 3 pairs, 2 of them clear 0.10 -> 0.6667.
    pairs = [(0.9, 0.15), (0.9, -0.05), (0.2, 0.15), (0.2, -0.05), (0.9, 0.2), (0.1, 0.0)]
    result = evaluate_predictive_power(pairs, score_threshold=0.5, success_threshold=0.10)
    assert result.n_total == 6
    assert result.n_signal == 3
    assert result.baseline_hit_rate == pytest.approx(0.5)
    assert result.signal_hit_rate == pytest.approx(2 / 3)
    assert result.edge == pytest.approx(2 / 3 - 0.5)


def test_evaluate_predictive_power_positive_edge_means_the_signal_actually_helped():
    # Every high-score pair is a hit, every low-score pair is a miss --
    # the clearest possible case of a real, useful signal.
    pairs = [(0.9, 0.20), (0.9, 0.15), (0.1, -0.05), (0.1, -0.10)]
    result = evaluate_predictive_power(pairs, score_threshold=0.5, success_threshold=0.10)
    assert result.signal_hit_rate == pytest.approx(1.0)
    assert result.baseline_hit_rate == pytest.approx(0.5)
    assert result.edge == pytest.approx(0.5)


def test_evaluate_predictive_power_zero_edge_means_the_signal_is_noise():
    # High score and low score have identical hit rates -- the score
    # carries no information about the outcome at all.
    pairs = [(0.9, 0.20), (0.9, -0.05), (0.1, 0.20), (0.1, -0.05)]
    result = evaluate_predictive_power(pairs, score_threshold=0.5, success_threshold=0.10)
    assert result.edge == pytest.approx(0.0)


def test_evaluate_predictive_power_empty_input():
    result = evaluate_predictive_power([], score_threshold=0.5, success_threshold=0.10)
    assert result == BacktestResult(n_total=0, n_signal=0, baseline_hit_rate=None, signal_hit_rate=None)
    assert result.edge is None


def test_evaluate_predictive_power_none_when_nothing_clears_the_score_threshold():
    pairs = [(0.1, 0.20), (0.2, -0.05)]
    result = evaluate_predictive_power(pairs, score_threshold=0.9, success_threshold=0.10)
    assert result.n_signal == 0
    assert result.signal_hit_rate is None
    assert result.edge is None
    # Baseline is still computable even though no point cleared the score bar.
    assert result.baseline_hit_rate == pytest.approx(0.5)


def _rising_series(n, dates_start=date(2020, 1, 1)):
    dates = [dates_start + timedelta(days=i) for i in range(n)]
    closes = [100.0 * (1.001 ** i) for i in range(n)]
    return dates, closes


def test_walk_history_produces_one_row_per_usable_day():
    n = 120
    horizon = 10
    dates, closes = _rising_series(n)
    rows = walk_history(closes, dates, horizon=horizon)
    # Usable days run from MIN_HISTORY_FOR_SCORE to n - 1 - horizon inclusive.
    expected = (n - 1 - horizon) - MIN_HISTORY_FOR_SCORE + 1
    assert len(rows) == expected


def test_walk_history_has_no_lookahead():
    # A row computed from the full series must be identical to one computed
    # from a series truncated right after the data that row's own
    # forward_return needed -- nothing further in the future may leak in.
    n = 120
    horizon = 10
    i = 80
    dates, closes = _rising_series(n)
    rows_full = walk_history(closes, dates, horizon=horizon)

    cutoff = i + horizon + 1  # exactly enough closes to compute forward_return at i
    rows_truncated = walk_history(closes[:cutoff], dates[:cutoff], horizon=horizon)

    idx = i - MIN_HISTORY_FOR_SCORE
    assert rows_full[idx] == rows_truncated[idx]


def test_walk_history_forward_return_matches_standalone_function():
    n = 120
    horizon = 10
    dates, closes = _rising_series(n)
    rows = walk_history(closes, dates, horizon=horizon)
    i = MIN_HISTORY_FOR_SCORE
    assert rows[0]["forward_return"] == pytest.approx(forward_return(closes, i, horizon))


def test_walk_history_market_trend_uses_spy_closes_as_of_that_day():
    n = 120
    horizon = 5
    dates, closes = _rising_series(n)
    _, spy_closes = _rising_series(n)  # also rising -- bullish market_trend throughout
    rows = walk_history(closes, dates, horizon=horizon, spy_closes=spy_closes)
    assert all(row["market_trend"] == pytest.approx(1.0) for row in rows)


def test_walk_history_market_trend_is_none_without_spy_closes():
    n = 120
    dates, closes = _rising_series(n)
    rows = walk_history(closes, dates, horizon=5)
    assert all(row["market_trend"] is None for row in rows)


def test_walk_history_seasonal_is_none_without_enough_years():
    # Only ~4 months of history -- nowhere near MIN_YEARS_FOR_SEASONAL_SIGNAL.
    n = 120
    dates, closes = _rising_series(n)
    rows = walk_history(closes, dates, horizon=5)
    assert all(row["seasonal"] is None for row in rows)


def test_walk_history_empty_when_no_day_has_enough_forward_history():
    dates, closes = _rising_series(MIN_HISTORY_FOR_SCORE)  # exactly the minimum, no room for a horizon
    assert walk_history(closes, dates, horizon=5) == []
