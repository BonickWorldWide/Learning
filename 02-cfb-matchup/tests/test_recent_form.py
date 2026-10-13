import pytest

import statistics

from cfb_matchup.models import Game
from cfb_matchup.recent_form import build_recent_form, common_opponents, scoring_std_dev, team_home_field_edge
from cfb_matchup.simulate import HOME_FIELD_ADVANTAGE


def _universe():
    return [
        Game(2024, 1, "2024-09-01", "Alpha", "Common1", 35, 14),
        Game(2024, 2, "2024-09-08", "Common2", "Alpha", 24, 20),
        Game(2024, 3, "2024-09-15", "Alpha", "OnlyAlphaOpp", 40, 10),
        Game(2024, 1, "2024-09-01", "Beta", "Common1", 28, 21),
        Game(2024, 2, "2024-09-08", "Common2", "Beta", 10, 17),
        Game(2024, 3, "2024-09-15", "Beta", "OnlyBetaOpp", 45, 7),
        Game(2024, 4, "2024-09-22", "RandomOpp", "Common1", 30, 10),
    ]


def test_alpha_record_and_scoring():
    form = build_recent_form(_universe(), "Alpha", [2024])
    assert form.games_played == 3
    assert (form.wins, form.losses) == (2, 1)
    assert form.points_for_per_game == pytest.approx(95 / 3)
    assert form.points_against_per_game == pytest.approx(48 / 3)


def test_alpha_home_away_splits():
    form = build_recent_form(_universe(), "Alpha", [2024])
    assert form.home_record == (2, 0)
    assert form.away_record == (0, 1)


def test_beta_record_and_scoring():
    form = build_recent_form(_universe(), "Beta", [2024])
    assert form.games_played == 3
    assert (form.wins, form.losses) == (3, 0)
    assert form.points_for_per_game == pytest.approx(30.0)
    assert form.points_against_per_game == pytest.approx(38 / 3)
    assert form.home_record == (2, 0)
    assert form.away_record == (1, 0)


def test_strength_of_schedule_uses_opponents_own_margins():
    form = build_recent_form(_universe(), "Alpha", [2024])
    # Common1 avg margin -16.0, Common2 avg margin -1.5, OnlyAlphaOpp -30.0
    assert form.strength_of_schedule == pytest.approx((-16.0 - 1.5 - 30.0) / 3)


def test_season_filter_excludes_other_seasons():
    games = _universe() + [Game(2020, 1, "2020-09-01", "Alpha", "Common1", 100, 0)]
    form = build_recent_form(games, "Alpha", [2024])
    assert form.games_played == 3  # the 2020 blowout must not leak in


def test_common_opponents_found_and_sorted():
    results = common_opponents(_universe(), "Alpha", "Beta", [2024])
    assert [r.opponent for r in results] == ["Common1", "Common2"]


def test_common_opponent_results_are_correct_per_team():
    results = common_opponents(_universe(), "Alpha", "Beta", [2024])
    common1 = next(r for r in results if r.opponent == "Common1")
    assert common1.team_a_won is True
    assert (common1.team_a_score, common1.team_a_opp_score) == (35, 14)
    assert common1.team_b_won is True
    assert (common1.team_b_score, common1.team_b_opp_score) == (28, 21)

    common2 = next(r for r in results if r.opponent == "Common2")
    assert common2.team_a_won is False
    assert (common2.team_a_score, common2.team_a_opp_score) == (20, 24)
    assert common2.team_b_won is True
    assert (common2.team_b_score, common2.team_b_opp_score) == (17, 10)


def test_opponent_played_by_only_one_team_is_excluded():
    results = common_opponents(_universe(), "Alpha", "Beta", [2024])
    names = {r.opponent for r in results}
    assert "OnlyAlphaOpp" not in names
    assert "OnlyBetaOpp" not in names
    assert "RandomOpp" not in names


def test_scoring_std_dev_matches_statistics_module():
    std = scoring_std_dev(_universe(), "Alpha", [2024])
    assert std == pytest.approx(statistics.stdev([35, 20, 40]))


def test_scoring_std_dev_falls_back_to_default_with_too_few_games():
    games = [Game(2024, 1, "2024-09-01", "Solo", "Opp", 30, 10)]
    assert scoring_std_dev(games, "Solo", [2024], default=12.5) == 12.5


def _home_away_games():
    # Zeta at home: margins +6, +8, +10 -> avg +8.
    # Zeta on the road: margins +2, +4, +6 -> avg +4.
    # Expected edge: (8 - 4) / 2 = 2.0 -- deliberately under the 5.0 clamp
    # ceiling (2x the 2.5 default) and not equal to the 2.5 default itself,
    # so this test actually exercises the hand-computed formula rather
    # than coincidentally matching either boundary.
    return [
        Game(2024, 1, "2024-09-01", "Zeta", "Opp1", 26, 20),
        Game(2024, 2, "2024-09-08", "Zeta", "Opp2", 28, 20),
        Game(2024, 3, "2024-09-15", "Zeta", "Opp3", 30, 20),
        Game(2024, 4, "2024-09-22", "Opp4", "Zeta", 18, 20),
        Game(2024, 5, "2024-09-29", "Opp5", "Zeta", 16, 20),
        Game(2024, 6, "2024-10-06", "Opp6", "Zeta", 14, 20),
    ]


def test_team_home_field_edge_matches_hand_calc():
    assert team_home_field_edge(_home_away_games(), "Zeta", [2024]) == pytest.approx(2.0)


def test_team_home_field_edge_falls_back_with_too_few_games_at_a_venue():
    # Alpha in _universe() has 2 home games and only 1 away game -- below
    # the default minimum of 3 at each venue.
    assert team_home_field_edge(_universe(), "Alpha", [2024]) == HOME_FIELD_ADVANTAGE


def test_team_home_field_edge_is_clamped_to_twice_league_average():
    # A tiny sample of blowouts both ways would otherwise imply an
    # enormous home-field edge -- clamped rather than trusted.
    extreme = [
        Game(2024, 1, "2024-09-01", "Zeta", "Opp1", 70, 0),
        Game(2024, 2, "2024-09-08", "Zeta", "Opp2", 70, 0),
        Game(2024, 3, "2024-09-15", "Zeta", "Opp3", 70, 0),
        Game(2024, 4, "2024-09-22", "Opp4", "Zeta", 70, 0),  # Zeta loses by 70 on the road
        Game(2024, 5, "2024-09-29", "Opp5", "Zeta", 70, 0),
        Game(2024, 6, "2024-10-06", "Opp6", "Zeta", 70, 0),
    ]
    assert team_home_field_edge(extreme, "Zeta", [2024], league_average=2.5) == pytest.approx(5.0)


def test_team_home_field_edge_never_goes_negative():
    # A team that's (over this small window) worse at home than away --
    # clamped to 0, never allowed to become a home-field *penalty*.
    worse_at_home = [
        Game(2024, 1, "2024-09-01", "Zeta", "Opp1", 10, 30),
        Game(2024, 2, "2024-09-08", "Zeta", "Opp2", 10, 30),
        Game(2024, 3, "2024-09-15", "Zeta", "Opp3", 10, 30),
        Game(2024, 4, "2024-09-22", "Opp4", "Zeta", 10, 30),  # Zeta wins by 20 on the road
        Game(2024, 5, "2024-09-29", "Opp5", "Zeta", 10, 30),
        Game(2024, 6, "2024-10-06", "Opp6", "Zeta", 10, 30),
    ]
    assert team_home_field_edge(worse_at_home, "Zeta", [2024]) == 0.0
