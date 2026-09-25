import pandas as pd

from fantasy_lineup.schedule import current_nfl_week, team_opponent_for_week


def _games_df():
    return pd.DataFrame(
        [
            {"season": 2026, "week": 1, "home_team": "BUF", "away_team": "NYJ", "home_score": 24.0, "away_score": 10.0},
            {"season": 2026, "week": 2, "home_team": "MIA", "away_team": "BUF", "home_score": 17.0, "away_score": 20.0},
            {"season": 2026, "week": 3, "home_team": "BUF", "away_team": "LAC", "home_score": None, "away_score": None},
            {"season": 2026, "week": 3, "home_team": "SF", "away_team": "SEA", "home_score": None, "away_score": None},
            {"season": 2025, "week": 1, "home_team": "BUF", "away_team": "ARI", "home_score": 30.0, "away_score": 20.0},
        ]
    )


def test_current_week_is_earliest_unplayed():
    assert current_nfl_week(_games_df(), 2026) == 3


def test_current_week_falls_back_to_last_week_when_season_complete():
    assert current_nfl_week(_games_df(), 2025) == 1


def test_opponent_found_when_team_is_home():
    assert team_opponent_for_week("SF", 2026, 3, _games_df()) == "SEA"


def test_opponent_found_when_team_is_away():
    assert team_opponent_for_week("LAC", 2026, 3, _games_df()) == "BUF"


def test_bye_week_returns_none():
    assert team_opponent_for_week("KC", 2026, 3, _games_df()) is None


def test_team_alias_is_normalized():
    # "OAK" should resolve the same as "LV" against normalized schedule data.
    games = pd.DataFrame(
        [{"season": 2026, "week": 3, "home_team": "LV", "away_team": "DEN", "home_score": None, "away_score": None}]
    )
    assert team_opponent_for_week("OAK", 2026, 3, games) == "DEN"
