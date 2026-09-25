import pytest

from cfb_matchup.simulate import simulate_game, win_prob_to_moneyline


def test_moneyline_even_money_at_fifty_percent():
    assert win_prob_to_moneyline(0.5) == -100


def test_moneyline_favorite_at_two_thirds():
    assert win_prob_to_moneyline(2 / 3) == -200


def test_moneyline_underdog_at_one_third():
    assert win_prob_to_moneyline(1 / 3) == 200


def test_moneyline_extreme_probabilities_are_clamped_not_infinite():
    # Should not raise or return inf/nan for a "sure thing".
    assert win_prob_to_moneyline(1.0) < -1000
    assert win_prob_to_moneyline(0.0) > 1000


def test_evenly_matched_teams_on_neutral_site_split_close_to_fifty_fifty():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        team_a_std=10.0, team_b_std=10.0, n_simulations=10_000,
        neutral_site=True, seed=42,
    )
    assert result.team_a_win_prob == pytest.approx(0.5, abs=0.03)
    assert result.projected_spread == pytest.approx(0.0, abs=1.5)


def test_same_seed_is_fully_reproducible():
    kwargs = dict(
        team_a="Alpha", team_b="Beta", team_a_expected=28.0, team_b_expected=24.0,
        team_a_std=9.0, team_b_std=11.0, n_simulations=5_000, seed=7,
    )
    result1 = simulate_game(**kwargs)
    result2 = simulate_game(**kwargs)
    assert result1 == result2


def test_home_field_advantage_helps_the_home_team():
    neutral = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        n_simulations=8_000, neutral_site=True, seed=1,
    )
    alpha_home = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        n_simulations=8_000, home_team="Alpha", seed=1,
    )
    assert alpha_home.team_a_win_prob > neutral.team_a_win_prob


def test_better_team_is_favored_with_correct_spread_direction():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=35.0, team_b_expected=17.0,
        team_a_std=8.0, team_b_std=8.0, n_simulations=10_000,
        neutral_site=True, seed=3,
    )
    assert result.team_a_win_prob > 0.9
    assert result.projected_spread > 10
    assert result.team_a_moneyline < 0  # favorite
    assert result.team_b_moneyline > 0  # underdog


def test_win_probabilities_sum_to_one():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=24.0, team_b_expected=31.0,
        n_simulations=5_000, seed=5,
    )
    assert result.team_a_win_prob + result.team_b_win_prob == pytest.approx(1.0)
