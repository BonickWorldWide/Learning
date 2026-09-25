import pytest

from cfb_matchup.models import Game
from cfb_matchup.power_rating import build_power_rating, season_margins, weighted_recent_margin


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
