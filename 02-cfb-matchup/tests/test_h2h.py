import pytest

from cfb_matchup.h2h import avg_combined_points, build_head_to_head, historical_over_rate
from cfb_matchup.models import Game

TEAM_A = "Alpha"
TEAM_B = "Beta"


def _series():
    # 7 meetings, hand-traceable: Alpha wins 4 (incl. a 2-game streak in
    # 2020-21), Beta wins 2 (one at a neutral site), 1 tie in 2024 that
    # should break any active streak.
    return [
        Game(2018, 1, "2018-09-01", "Alpha", "Beta", 30, 20, neutral_site=False),
        Game(2019, 1, "2019-09-01", "Beta", "Alpha", 24, 21, neutral_site=False),
        Game(2020, 1, "2020-09-01", "Alpha", "Beta", 35, 14, neutral_site=False),
        Game(2021, 1, "2021-09-01", "Beta", "Alpha", 27, 28, neutral_site=False),
        Game(2022, 1, "2022-09-01", "Alpha", "Beta", 17, 20, neutral_site=True),
        Game(2023, 1, "2023-09-01", "Alpha", "Beta", 40, 10, neutral_site=False),
        Game(2024, 1, "2024-09-01", "Beta", "Alpha", 21, 21, neutral_site=False),
    ]


def test_all_time_record_and_margins():
    summary = build_head_to_head(_series(), TEAM_A, TEAM_B)
    at = summary.all_time
    assert at.games == 7
    assert at.team_a_wins == 4
    assert at.team_b_wins == 2
    assert at.ties == 1
    assert at.avg_margin_team_a == pytest.approx(15.5)
    assert at.avg_margin_team_b == pytest.approx(3.0)


def test_last_10_and_last_20_equal_all_time_when_fewer_meetings_exist():
    summary = build_head_to_head(_series(), TEAM_A, TEAM_B)
    assert summary.last_10.games == 7
    assert summary.last_20.games == 7


def test_last_10_windows_to_most_recent_meetings_only():
    games = [
        Game(2000 + i, 1, f"{2000+i}-09-01", "Alpha", "Beta", 30, 10, neutral_site=False)
        for i in range(15)
    ]
    # Make the 5 oldest meetings Beta wins so they'd change the all-time
    # record but must NOT show up in last_10.
    for g in games[:5]:
        g.home_score, g.away_score = 10, 30

    summary = build_head_to_head(games, TEAM_A, TEAM_B)
    assert summary.all_time.games == 15
    assert summary.all_time.team_b_wins == 5
    assert summary.last_10.games == 10
    assert summary.last_10.team_b_wins == 0  # none of the Beta wins are in the last 10


def test_venue_splits_for_team_a():
    summary = build_head_to_head(_series(), TEAM_A, TEAM_B)
    home = summary.team_a_venue_splits["home"]
    assert (home.wins, home.losses, home.ties) == (3, 0, 0)
    assert home.avg_margin == pytest.approx(61 / 3)

    away = summary.team_a_venue_splits["away"]
    assert (away.wins, away.losses, away.ties) == (1, 1, 1)
    assert away.avg_margin == pytest.approx(-2 / 3)

    neutral = summary.team_a_venue_splits["neutral"]
    assert (neutral.wins, neutral.losses, neutral.ties) == (0, 1, 0)
    assert neutral.avg_margin == pytest.approx(-3.0)


def test_venue_splits_for_team_b_mirror_team_a():
    summary = build_head_to_head(_series(), TEAM_A, TEAM_B)
    # Team B's "home" games are Team A's "away" games and vice versa.
    b_home = summary.team_b_venue_splits["home"]
    assert (b_home.wins, b_home.losses, b_home.ties) == (1, 1, 1)
    assert b_home.avg_margin == pytest.approx(2 / 3)

    b_away = summary.team_b_venue_splits["away"]
    assert (b_away.wins, b_away.losses, b_away.ties) == (0, 3, 0)
    assert b_away.avg_margin == pytest.approx(-61 / 3)


def test_longest_and_current_streak():
    summary = build_head_to_head(_series(), TEAM_A, TEAM_B)
    assert summary.longest_streak_team == "Alpha"
    assert summary.longest_streak_len == 2
    # Most recent meeting was a tie -> no active streak.
    assert summary.current_streak_team is None
    assert summary.current_streak_len == 0


def test_current_streak_when_last_game_was_a_win():
    games = _series()[:-1]  # drop the final tie
    summary = build_head_to_head(games, TEAM_A, TEAM_B)
    assert summary.current_streak_team == "Alpha"
    assert summary.current_streak_len == 1


def test_avg_combined_points_and_over_rate():
    games = _series()
    assert avg_combined_points(games) == pytest.approx(328 / 7)
    assert historical_over_rate(games, 45) == pytest.approx(4 / 7)


def test_empty_history_between_teams_that_never_played():
    summary = build_head_to_head(_series(), "Alpha", "Nobody FC")
    assert summary.all_time.games == 0
    assert summary.rarely_play is True
    assert summary.small_sample is True
