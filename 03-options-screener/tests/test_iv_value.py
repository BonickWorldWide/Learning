import pytest

from options_screener.iv_value import iv_realized_ratio, iv_value_score


def test_iv_realized_ratio_one_means_priced_in_line_with_reality():
    assert iv_realized_ratio(0.40, 0.40) == pytest.approx(1.0)


def test_iv_realized_ratio_above_one_means_rich():
    assert iv_realized_ratio(0.60, 0.30) == pytest.approx(2.0)


def test_iv_realized_ratio_below_one_means_cheap():
    assert iv_realized_ratio(0.20, 0.40) == pytest.approx(0.5)


def test_iv_realized_ratio_none_when_realized_volatility_is_none():
    assert iv_realized_ratio(0.40, None) is None


def test_iv_realized_ratio_none_when_realized_volatility_is_zero_or_negative():
    assert iv_realized_ratio(0.40, 0.0) is None
    assert iv_realized_ratio(0.40, -0.1) is None


def test_iv_value_score_full_score_at_or_below_cheap_ceiling():
    assert iv_value_score(1.0, cheap_ceiling=1.0, rich_floor=2.0) == 1.0
    assert iv_value_score(0.5, cheap_ceiling=1.0, rich_floor=2.0) == 1.0


def test_iv_value_score_zero_at_or_above_rich_floor():
    assert iv_value_score(2.0, cheap_ceiling=1.0, rich_floor=2.0) == 0.0
    assert iv_value_score(3.0, cheap_ceiling=1.0, rich_floor=2.0) == 0.0


def test_iv_value_score_linear_between_ceiling_and_floor():
    # Halfway between 1.0 and 2.0 (1.5) should score 0.5.
    assert iv_value_score(1.5, cheap_ceiling=1.0, rich_floor=2.0) == pytest.approx(0.5)


def test_iv_value_score_none_when_ratio_is_none():
    assert iv_value_score(None, cheap_ceiling=1.0, rich_floor=2.0) is None


def test_iv_value_score_inverted_vs_movement_score():
    # Unlike movement_score/jump_score, a LOWER raw number scores higher here.
    cheap = iv_value_score(0.6, cheap_ceiling=1.0, rich_floor=2.0)
    rich = iv_value_score(1.8, cheap_ceiling=1.0, rich_floor=2.0)
    assert cheap > rich
