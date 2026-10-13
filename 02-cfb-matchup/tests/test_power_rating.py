import pytest

from cfb_matchup.models import Game
from cfb_matchup.power_rating import (
    LEAGUE_AVERAGE_PLAYS_PER_GAME,
    build_power_rating,
    game_pace_factor,
    pace_factor,
    plays_per_game,
    season_margins,
    weighted_recent_margin,
)


def _games():
    return [
        Game(2024, 1, "2024-09-01", "Alpha", "X", 30, 10),  # margin +20
        Game(2023, 1, "2023-09-01", "Alpha", "Y", 20, 17),  # margin +3
        Game(2022, 1, "2022-09-01", "Alpha", "Z", 14, 21),  # margin -7
        Game(2021, 1, "2021-09-01", "Alpha", "W", 24, 14),  # margin +10
    ]


def test_season_margins_one_per_season():
    margins = season_margins(_games(), "Alpha", [2024, 2023, 2022, 2021])
    assert margins == {2024: 20, 2023: 3, 2022: -7, 2021: 10}


def test_weighted_recent_margin_matches_hand_calc():
    # weights [0.5, 0.3, 0.2]: 20*0.5 + 3*0.3 + (-7)*0.2 = 9.5
    margin = weighted_recent_margin(_games(), "Alpha", [2024, 2023, 2022])
    assert margin == pytest.approx(9.5)


def test_weighted_recent_margin_skips_a_season_not_played():
    # No 2020 game -> only 2024 (0.5) and 2023 (0.3) weights are used, renormalized.
    margin = weighted_recent_margin(_games(), "Alpha", [2024, 2023, 2020])
    assert margin == pytest.approx((20 * 0.5 + 3 * 0.3) / 0.8)


def test_weighted_recent_margin_repeats_last_weight_beyond_the_list():
    # 4 seasons given but only 3 weights defined -> the 4th (oldest, 2021)
    # reuses the last weight (0.2) rather than being dropped or erroring.
    margin = weighted_recent_margin(_games(), "Alpha", [2024, 2023, 2022, 2021])
    expected = (20 * 0.5 + 3 * 0.3 + (-7) * 0.2 + 10 * 0.2) / (0.5 + 0.3 + 0.2 + 0.2)
    assert margin == pytest.approx(expected)


def test_power_rating_combines_margin_and_sos():
    rating = build_power_rating(_games(), "Alpha", [2024, 2023, 2022], strength_of_schedule=8.0)
    # margin 9.5 + (8.0 * SOS_WEIGHT=0.25 -> 2.0) = 11.5
    assert rating.rating == pytest.approx(11.5)
    assert rating.expected_points == pytest.approx(27.0 + 11.5 / 2)
    assert rating.components["recency_weighted_margin"] == pytest.approx(9.5)
    assert rating.components["strength_of_schedule_adjustment"] == pytest.approx(2.0)


def test_power_rating_blends_external_rating_when_given():
    rating = build_power_rating(
        _games(), "Alpha", [2024, 2023, 2022], strength_of_schedule=8.0, external_rating=20.0
    )
    # own calc 11.5, blended 60/40 with external 20.0: 11.5*0.6 + 20.0*0.4 = 14.9
    assert rating.rating == pytest.approx(14.9)
    assert rating.components["external_rating"] == 20.0


def test_power_rating_with_no_games_defaults_to_baseline():
    rating = build_power_rating([], "Nobody", [2024], strength_of_schedule=None)
    assert rating.rating == pytest.approx(0.0)
    assert rating.expected_points == pytest.approx(27.0)


def test_plays_per_game_divides_total_by_games_played():
    assert plays_per_game(700, 10) == pytest.approx(70.0)


def test_plays_per_game_none_when_either_input_is_missing_or_zero():
    assert plays_per_game(None, 10) is None
    assert plays_per_game(700, 0) is None


def test_pace_factor_matches_league_average_at_exactly_one():
    assert pace_factor(LEAGUE_AVERAGE_PLAYS_PER_GAME) == pytest.approx(1.0)


def test_pace_factor_below_one_for_a_slow_tempo_team():
    # Navy-style triple option: well under the league-average play count.
    assert pace_factor(60.0) < 1.0


def test_pace_factor_above_one_for_a_fast_tempo_team():
    assert pace_factor(85.0) > 1.0


def test_pace_factor_treats_missing_data_as_exactly_average():
    assert pace_factor(None) == pytest.approx(1.0)


def test_game_pace_factor_is_the_average_of_both_teams_own_factors():
    # 60 and 80 plays/game -> individual factors 60/70 and 80/70, averaged.
    expected = (pace_factor(60.0) + pace_factor(80.0)) / 2
    assert game_pace_factor(60.0, 80.0) == pytest.approx(expected)


def test_game_pace_factor_with_one_team_missing_pace_data():
    # Missing data treated as average (1.0) for that team only.
    assert game_pace_factor(60.0, None) == pytest.approx((pace_factor(60.0) + 1.0) / 2)


def test_game_pace_factor_is_a_true_no_op_when_neither_team_has_pace_data():
    # This exact value is what analysis.py multiplies both teams' expected
    # points by when no pace data exists for either -- it must be exactly
    # 1.0, not merely close to it, since every existing report (and test)
    # before this feature existed depends on that.
    assert game_pace_factor(None, None) == 1.0


def test_power_rating_pace_adjustment_boosts_a_slow_tempo_teams_margin():
    # A slow-tempo team's raw margin should be scaled *up* once pace-adjusted
    # -- the same margin with fewer possessions implies better per-play quality.
    without_pace = build_power_rating(_games(), "Alpha", [2024, 2023, 2022], strength_of_schedule=0.0)
    with_slow_pace = build_power_rating(
        _games(), "Alpha", [2024, 2023, 2022], strength_of_schedule=0.0, team_plays_per_game=60.0,
    )
    assert with_slow_pace.components["recency_weighted_margin"] > without_pace.components["recency_weighted_margin"]
    assert with_slow_pace.components["pace_factor"] == pytest.approx(pace_factor(60.0))


def test_power_rating_omitting_pace_data_is_unchanged_from_before_the_feature_existed():
    # No team_plays_per_game at all -- must be identical to a plain call,
    # since every existing caller (and test) relies on this being a no-op.
    rating = build_power_rating(_games(), "Alpha", [2024, 2023, 2022], strength_of_schedule=8.0)
    assert rating.rating == pytest.approx(11.5)
    assert "pace_factor" not in rating.components
