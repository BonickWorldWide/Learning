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


def test_no_vegas_line_leaves_cover_and_total_fields_none():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=24.0, n_simulations=2_000, seed=1,
    )
    assert result.vegas_spread is None
    assert result.vegas_total is None
    assert result.team_a_cover_prob is None
    assert result.team_b_cover_prob is None
    assert result.over_prob is None
    assert result.under_prob is None


def test_favorite_beating_a_soft_line_covers_more_often_than_not():
    # Model projects Alpha by ~10 -- a real line of only +7 for Alpha should
    # mean Alpha covers in well over half of the simulated trials.
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=31.0, team_b_expected=21.0,
        team_a_std=10.0, team_b_std=10.0, n_simulations=20_000,
        neutral_site=True, seed=1, vegas_spread=7.0,
    )
    assert result.team_a_cover_prob > 0.55
    assert result.team_a_cover_prob + result.team_b_cover_prob == pytest.approx(1.0)


def test_favorite_facing_a_tough_line_covers_less_often():
    # Same model projection, but the line already demands a much bigger
    # margin (15) than the model expects (~10) -- Alpha should cover less
    # than half the time against a line that steep.
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=31.0, team_b_expected=21.0,
        team_a_std=10.0, team_b_std=10.0, n_simulations=20_000,
        neutral_site=True, seed=1, vegas_spread=15.0,
    )
    assert result.team_a_cover_prob < 0.5


def test_total_over_under_probabilities_sum_to_one_and_match_the_projection():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=31.0, team_b_expected=21.0,
        team_a_std=10.0, team_b_std=10.0, n_simulations=20_000,
        neutral_site=True, seed=1, vegas_total=40.0,  # well under the ~52 projected total
    )
    assert result.over_prob + result.under_prob == pytest.approx(1.0)
    assert result.over_prob > 0.5  # a total well below the projection should go over more often than not
