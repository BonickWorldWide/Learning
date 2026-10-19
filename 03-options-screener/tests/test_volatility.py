import math

import pytest

from options_screener.volatility import jump_score, large_move_frequency, movement_score, realized_volatility


def test_realized_volatility_is_zero_for_a_flat_price():
    closes = [100.0] * 25
    assert realized_volatility(closes, window=20) == pytest.approx(0.0)


def test_realized_volatility_matches_hand_calc():
    # Two log returns, +4.879% then -4.879% -- mean 0, sample stdev
    # computed directly, then annualized by sqrt(252).
    closes = [100.0, 105.0, 100.0]
    r1 = math.log(105.0 / 100.0)
    r2 = math.log(100.0 / 105.0)
    mean = (r1 + r2) / 2
    variance = ((r1 - mean) ** 2 + (r2 - mean) ** 2) / 1  # n-1 = 1
    expected = math.sqrt(variance) * math.sqrt(252)
    assert realized_volatility(closes, window=2) == pytest.approx(expected)


def test_realized_volatility_none_with_too_little_history():
    closes = [100.0] * 20  # window=20 needs 21 closes
    assert realized_volatility(closes, window=20) is None


def test_realized_volatility_a_bigger_swing_scores_higher():
    calm = [100.0, 101.0, 100.0] * 10
    wild = [100.0, 140.0, 100.0] * 10
    assert realized_volatility(wild, window=20) > realized_volatility(calm, window=20)


def test_movement_score_at_or_below_floor_is_zero():
    assert movement_score(0.20, floor=0.35, ceiling=0.80) == 0.0
    assert movement_score(0.35, floor=0.35, ceiling=0.80) == 0.0


def test_movement_score_at_or_above_ceiling_is_one():
    assert movement_score(0.80, floor=0.35, ceiling=0.80) == 1.0
    assert movement_score(1.50, floor=0.35, ceiling=0.80) == 1.0


def test_movement_score_linear_between_floor_and_ceiling():
    # Halfway between 0.35 and 0.80 (0.575) should score 0.5.
    assert movement_score(0.575, floor=0.35, ceiling=0.80) == pytest.approx(0.5)


def test_movement_score_none_when_volatility_is_none():
    assert movement_score(None, floor=0.35, ceiling=0.80) is None


def test_large_move_frequency_matches_hand_calc():
    # 10 flat closes (9 zero-move days), then one +10% day, then one -2%
    # day -- 11 daily returns total, only the +10% one clears a 5%
    # threshold (the -2% day doesn't).
    closes = [100.0] * 10 + [110.0, 107.8]
    assert large_move_frequency(closes, threshold=0.05) == pytest.approx(1 / 11)


def test_large_move_frequency_zero_for_a_stock_that_never_jumps():
    closes = [100.0, 101.0, 100.0, 101.0, 100.0]
    assert large_move_frequency(closes, threshold=0.05) == pytest.approx(0.0)


def test_large_move_frequency_distinguishes_jumpy_from_merely_volatile():
    # Same total variance-ish range, but one moves in small steps every
    # day (no single day clears 5%) and the other sits still then jumps.
    gradual = [100.0 * (1.01 ** i) for i in range(30)]  # ~1%/day compounding, never a single big day
    jumpy = [100.0] * 25 + [120.0] + [100.0] * 4  # one +20% day, rest flat
    assert large_move_frequency(jumpy, threshold=0.05) > large_move_frequency(gradual, threshold=0.05)


def test_large_move_frequency_none_with_fewer_than_two_closes():
    assert large_move_frequency([100.0]) is None


def test_large_move_frequency_respects_window():
    # A big move far in the past, outside the window, shouldn't count.
    closes = [100.0, 150.0] + [100.0] * 25
    assert large_move_frequency(closes, threshold=0.05, window=20) == pytest.approx(0.0)


def test_jump_score_zero_at_zero_frequency():
    assert jump_score(0.0, ceiling=0.04) == 0.0


def test_jump_score_one_at_or_above_ceiling():
    assert jump_score(0.04, ceiling=0.04) == 1.0
    assert jump_score(0.10, ceiling=0.04) == 1.0


def test_jump_score_linear_below_ceiling():
    assert jump_score(0.02, ceiling=0.04) == pytest.approx(0.5)


def test_jump_score_none_when_frequency_is_none():
    assert jump_score(None, ceiling=0.04) is None
