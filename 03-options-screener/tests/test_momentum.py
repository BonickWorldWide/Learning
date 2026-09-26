import pytest

from options_screener.models import MomentumResult
from options_screener.momentum import build_momentum


def test_all_up_days_gives_rsi_100():
    closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]  # 14 consecutive +1 days
    result = build_momentum(closes)
    assert result.rsi_14 == 100.0


def test_all_down_days_gives_rsi_0():
    closes = list(range(15, 0, -1))  # 14 consecutive -1 days
    result = build_momentum(closes)
    assert result.rsi_14 == 0.0


def test_evenly_split_gains_and_losses_gives_rsi_50():
    closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10]
    result = build_momentum(closes)
    assert result.rsi_14 == pytest.approx(50.0)


def test_return_20d_is_none_with_too_little_history():
    result = build_momentum([1.0] * 15)
    assert result.return_20d is None


def test_return_20d_computed_correctly():
    closes = [float(x) for x in range(1, 26)]  # 25 days, 1..25
    result = build_momentum(closes)
    assert result.return_20d == pytest.approx((25 - 5) / 5)


def test_above_50sma_true_when_last_close_beats_the_average():
    closes = [100.0] * 49 + [110.0]
    result = build_momentum(closes)
    assert result.above_50sma is True


def test_above_50sma_false_when_last_close_is_below_the_average():
    closes = [100.0] * 49 + [90.0]
    result = build_momentum(closes)
    assert result.above_50sma is False


def test_above_50sma_none_with_too_little_history():
    result = build_momentum([100.0] * 10)
    assert result.above_50sma is None


def test_bullish_score_all_bullish_signals_is_one():
    result = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)
    assert result.bullish_score == pytest.approx(1.0)


def test_bullish_score_all_bearish_signals_is_zero():
    result = MomentumResult(return_20d=-0.1, rsi_14=30, above_50sma=False)
    assert result.bullish_score == pytest.approx(0.0)


def test_bullish_score_neutral_rsi_counts_as_half():
    result = MomentumResult(return_20d=None, rsi_14=50, above_50sma=None)
    assert result.bullish_score == pytest.approx(0.5)


def test_bullish_score_defaults_to_half_with_no_signals_available():
    result = MomentumResult(return_20d=None, rsi_14=None, above_50sma=None)
    assert result.bullish_score == pytest.approx(0.5)
