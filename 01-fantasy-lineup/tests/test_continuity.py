import pandas as pd

from fantasy_lineup.continuity import build_continuity


def _games_df():
    return pd.DataFrame(
        [
            # Historical meetings vs SEA, with old coach and old QB
            {"season": 2021, "week": 3, "home_team": "SF", "away_team": "SEA",
             "home_score": 20.0, "away_score": 10.0,
             "home_coach": "Old Coach", "away_coach": "Pete Carroll",
             "home_qb_name": "Old QB", "away_qb_name": "Russell Wilson"},
            {"season": 2022, "week": 8, "home_team": "SEA", "away_team": "SF",
             "home_score": 21.0, "away_score": 13.0,
             "home_coach": "Pete Carroll", "away_coach": "Old Coach",
             "home_qb_name": "Geno Smith", "away_qb_name": "Old QB"},
            # This season: new coach and new QB have started (rows before and after "now")
            {"season": 2024, "week": 1, "home_team": "SF", "away_team": "ARI",
             "home_score": 30.0, "away_score": 12.0,
             "home_coach": "New Coach", "away_coach": "Jonathan Gannon",
             "home_qb_name": "New QB", "away_qb_name": "Kyler Murray"},
            {"season": 2024, "week": 4, "home_team": "SF", "away_team": "SEA",
             "home_score": None, "away_score": None,  # not played yet
             "home_coach": "New Coach", "away_coach": "Mike Macdonald",
             "home_qb_name": None, "away_qb_name": None},
        ]
    )


def test_detects_head_coach_change():
    flags = build_continuity(_games_df(), team="SF", opponent="SEA", current_season=2024,
                              historical_seasons=[2021, 2022])
    assert flags.current_coach == "New Coach"
    assert flags.prior_coaches == ["Old Coach"]
    assert flags.head_coach_changed is True


def test_detects_qb_change_using_latest_played_game():
    flags = build_continuity(_games_df(), team="SF", opponent="SEA", current_season=2024,
                              historical_seasons=[2021, 2022])
    assert flags.current_qb == "New QB"
    assert flags.prior_qbs == ["Old QB"]
    assert flags.qb_changed is True


def test_no_change_when_same_coach_and_qb():
    games = pd.DataFrame(
        [
            {"season": 2022, "week": 8, "home_team": "SEA", "away_team": "SF",
             "home_score": 21.0, "away_score": 13.0,
             "home_coach": "Pete Carroll", "away_coach": "Same Coach",
             "home_qb_name": "Geno Smith", "away_qb_name": "Same QB"},
            {"season": 2024, "week": 1, "home_team": "SF", "away_team": "ARI",
             "home_score": 30.0, "away_score": 12.0,
             "home_coach": "Same Coach", "away_coach": "Jonathan Gannon",
             "home_qb_name": "Same QB", "away_qb_name": "Kyler Murray"},
        ]
    )
    flags = build_continuity(games, team="SF", opponent="SEA", current_season=2024, historical_seasons=[2022])
    assert flags.head_coach_changed is False
    assert flags.qb_changed is False


def test_no_games_played_yet_this_season_adds_a_note():
    games = pd.DataFrame(
        [
            {"season": 2024, "week": 1, "home_team": "SF", "away_team": "SEA",
             "home_score": None, "away_score": None,
             "home_coach": "Coach", "away_coach": "Other Coach",
             "home_qb_name": None, "away_qb_name": None},
        ]
    )
    flags = build_continuity(games, team="SF", opponent="SEA", current_season=2024, historical_seasons=[])
    assert flags.current_qb is None
    assert any("no games played yet" in note for note in flags.notes)
