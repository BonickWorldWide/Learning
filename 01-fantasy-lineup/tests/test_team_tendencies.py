import pandas as pd
import pytest

from fantasy_lineup.team_tendencies import build_team_tendency


def _weekly_df():
    rows = [
        # Game 1: 2023 week 1, SF at SEA (from SF's perspective as "recent_team")
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2023, "week": 1, "position": "QB",
         "player_name": "QB One", "attempts": 30, "carries": 3, "passing_yards": 250, "rushing_yards": 5,
         "targets": 0},
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2023, "week": 1, "position": "RB",
         "player_name": "RB One", "attempts": 0, "carries": 15, "passing_yards": 0, "rushing_yards": 70,
         "targets": 4},
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2023, "week": 1, "position": "WR",
         "player_name": "WR One", "attempts": 0, "carries": 0, "passing_yards": 0, "rushing_yards": 0,
         "targets": 8},
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2023, "week": 1, "position": "TE",
         "player_name": "TE One", "attempts": 0, "carries": 0, "passing_yards": 0, "rushing_yards": 0,
         "targets": 3},
        # Game 2: 2024 week 5, SF hosts SEA
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2024, "week": 5, "position": "QB",
         "player_name": "QB One", "attempts": 20, "carries": 1, "passing_yards": 210, "rushing_yards": 2,
         "targets": 0},
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2024, "week": 5, "position": "RB",
         "player_name": "RB One", "attempts": 0, "carries": 25, "passing_yards": 0, "rushing_yards": 110,
         "targets": 2},
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2024, "week": 5, "position": "WR",
         "player_name": "WR One", "attempts": 0, "carries": 0, "passing_yards": 0, "rushing_yards": 0,
         "targets": 6},
        {"recent_team": "SF", "opponent_team": "SEA", "season": 2024, "week": 5, "position": "TE",
         "player_name": "TE One", "attempts": 0, "carries": 0, "passing_yards": 0, "rushing_yards": 0,
         "targets": 2},
        # A game against a different opponent — must not leak into SF-vs-SEA numbers.
        {"recent_team": "SF", "opponent_team": "DAL", "season": 2024, "week": 9, "position": "RB",
         "player_name": "RB One", "attempts": 0, "carries": 40, "passing_yards": 0, "rushing_yards": 200,
         "targets": 0},
    ]
    return pd.DataFrame(rows)


def _games_df():
    return pd.DataFrame(
        [
            {"season": 2023, "week": 1, "home_team": "SF", "away_team": "SEA", "home_score": 24, "away_score": 17},
            {"season": 2024, "week": 5, "home_team": "SEA", "away_team": "SF", "home_score": 10, "away_score": 31},
        ]
    )


def test_games_count_and_seasons_scoped_to_this_matchup():
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "SEA", seasons=[2023, 2024])
    assert t.games == 2  # not 3 — the DAL game must not count


def test_run_rate_is_average_of_per_game_rates():
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "SEA", seasons=[2023, 2024])
    # game 1: rush_att=3+15=18, pass_att=30 -> 18/48
    # game 2: rush_att=1+25=26, pass_att=20 -> 26/46
    expected = ((18 / 48) + (26 / 46)) / 2
    assert t.run_rate == pytest.approx(expected)
    assert t.pass_rate == pytest.approx(1 - expected)


def test_avg_points_for_handles_home_and_away_games():
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "SEA", seasons=[2023, 2024])
    assert t.avg_points_for == pytest.approx((24 + 31) / 2)


def test_position_volume_share_sums_to_one():
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "SEA", seasons=[2023, 2024])
    assert sum(t.position_volume_share.values()) == pytest.approx(1.0)
    # RB carried the most volume across both games (targets+carries)
    assert max(t.position_volume_share, key=t.position_volume_share.get) == "RB"


def test_top_volume_player_identified_per_position():
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "SEA", seasons=[2023, 2024])
    assert t.top_volume_player["RB"] == "RB One"
    assert t.top_volume_player["WR"] == "WR One"


def test_no_games_returns_empty_tendency():
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "NYG", seasons=[2023, 2024])
    assert t.games == 0
    assert t.run_rate is None
    assert t.has_history is False


def test_small_sample_flag():
    # SF-vs-SEA fixture has 2 games -> below the 3-game threshold.
    t = build_team_tendency(_weekly_df(), _games_df(), "SF", "SEA", seasons=[2023, 2024])
    assert t.games == 2
    assert t.small_sample is True


def test_not_small_sample_at_three_games():
    third_game = pd.DataFrame(
        [
            {"recent_team": "SF", "opponent_team": "SEA", "season": 2025, "week": 2, "position": "RB",
             "player_name": "RB One", "attempts": 0, "carries": 20, "passing_yards": 0, "rushing_yards": 80,
             "targets": 3},
        ]
    )
    weekly = pd.concat([_weekly_df(), third_game], ignore_index=True)
    game_row = pd.DataFrame(
        [{"season": 2025, "week": 2, "home_team": "SF", "away_team": "SEA", "home_score": 20, "away_score": 14}]
    )
    games = pd.concat([_games_df(), game_row], ignore_index=True)

    t = build_team_tendency(weekly, games, "SF", "SEA", seasons=[2023, 2024, 2025])
    assert t.games == 3
    assert t.small_sample is False
