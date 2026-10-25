import pytest

from cfb_matchup.simulate import (
    HOME_FIELD_ADVANTAGE,
    moneyline_ev,
    moneyline_to_implied_prob,
    simulate_game,
    win_prob_to_moneyline,
)


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


def test_default_home_edge_is_the_flat_league_constant():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0, n_simulations=1_000, seed=1,
    )
    assert result.team_a_home_edge == HOME_FIELD_ADVANTAGE
    assert result.team_b_home_edge == HOME_FIELD_ADVANTAGE


def test_custom_home_edge_is_echoed_back_on_the_result():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0, n_simulations=1_000, seed=1,
        team_a_home_edge=5.0, team_b_home_edge=1.0,
    )
    assert result.team_a_home_edge == 5.0
    assert result.team_b_home_edge == 1.0


def test_a_bigger_team_specific_home_edge_helps_the_host_more_than_the_flat_default():
    flat_default = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        n_simulations=8_000, home_team="Alpha", seed=1,
    )
    big_home_edge = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        n_simulations=8_000, home_team="Alpha", seed=1, team_a_home_edge=8.0,
    )
    assert big_home_edge.team_a_win_prob > flat_default.team_a_win_prob


def test_home_edge_only_applies_to_whoever_is_actually_hosting():
    # Alpha has a huge home-field number, but Beta is the one hosting --
    # Alpha's own home_edge must not help them on the road.
    away_with_big_edge = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        n_simulations=8_000, home_team="Beta", seed=1, team_a_home_edge=20.0,
    )
    neutral = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0,
        n_simulations=8_000, neutral_site=True, seed=1,
    )
    assert away_with_big_edge.team_a_win_prob < neutral.team_a_win_prob  # Beta hosting still helps Beta, not Alpha


def test_neutral_site_ignores_both_teams_home_edge():
    result = simulate_game(
        "Alpha", "Beta", team_a_expected=27.0, team_b_expected=27.0, n_simulations=1_000,
        neutral_site=True, seed=1, team_a_home_edge=20.0, team_b_home_edge=20.0,
    )
    assert result.team_a_win_prob == pytest.approx(0.5, abs=0.05)


def test_moneyline_to_implied_prob_matches_hand_calc():
    assert moneyline_to_implied_prob(-400) == pytest.approx(400 / 500)  # 80%
    assert moneyline_to_implied_prob(200) == pytest.approx(100 / 300)  # 33.3%
    assert moneyline_to_implied_prob(-110) == pytest.approx(110 / 210)  # 52.4%, standard vig
    assert moneyline_to_implied_prob(100) == pytest.approx(0.5)


def test_moneyline_to_implied_prob_is_the_inverse_direction_of_win_prob_to_moneyline():
    # Round-tripping a FAIR (vig-free) line should return (close to) the
    # original probability -- win_prob_to_moneyline strips no vig, so
    # there's nothing for the inverse to add back.
    for prob in (0.5, 0.6, 0.75, 0.33):
        odds = win_prob_to_moneyline(prob)
        assert moneyline_to_implied_prob(odds) == pytest.approx(prob, abs=0.01)


def test_moneyline_ev_matches_hand_calc_for_a_favorite():
    # Georgia Tech at -230: if the model's real win probability is 75%
    # (a real edge over the market's implied 69.7%), the bet should be
    # profitable on average.
    payout = 100 * 100 / 230
    expected = 0.75 * payout - 0.25 * 100
    assert moneyline_ev(0.75, -230, stake=100) == pytest.approx(expected)
    assert moneyline_ev(0.75, -230, stake=100) > 0


def test_moneyline_ev_is_zero_when_the_true_probability_exactly_matches_the_market():
    # TCU at -400 implies an 80% win probability -- if the model agrees
    # exactly, there's no edge in either direction, win or lose.
    implied = moneyline_to_implied_prob(-400)
    assert moneyline_ev(implied, -400, stake=100) == pytest.approx(0.0, abs=0.01)


def test_moneyline_ev_negative_when_true_probability_is_below_the_market_implied_one():
    # This is the real-world case that actually lost money: betting a
    # heavy favorite ("to win") even though the model's own probability
    # doesn't clear what that price demands.
    implied = moneyline_to_implied_prob(-230)
    assert moneyline_ev(implied - 0.10, -230, stake=100) < 0


def test_moneyline_ev_positive_for_a_value_underdog():
    # +185 implies ~35.1% -- a model giving this team 45% is real value.
    ev = moneyline_ev(0.45, 185, stake=100)
    payout = 100 * 185 / 100
    expected = 0.45 * payout - 0.55 * 100
    assert ev == pytest.approx(expected)
    assert ev > 0


def test_moneyline_ev_scales_with_stake():
    ev_100 = moneyline_ev(0.75, -230, stake=100)
    ev_200 = moneyline_ev(0.75, -230, stake=200)
    assert ev_200 == pytest.approx(ev_100 * 2)
