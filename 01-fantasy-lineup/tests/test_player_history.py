import pandas as pd

from fantasy_lineup.player_history import build_player_history


def _weekly_df():
    # A WR ("00-1") with 4 career games: 2 against KC (opponent), 2 against others.
    return pd.DataFrame(
        [
            {"player_id": "00-1", "season": 2023, "week": 1, "opponent_team": "KC",
             "targets": 10, "receptions": 8, "receiving_yards": 120, "receiving_tds": 1},
            {"player_id": "00-1", "season": 2023, "week": 5, "opponent_team": "KC",
             "targets": 9, "receptions": 6, "receiving_yards": 90, "receiving_tds": 1},
            {"player_id": "00-1", "season": 2024, "week": 2, "opponent_team": "DEN",
             "targets": 5, "receptions": 3, "receiving_yards": 40, "receiving_tds": 0},
            {"player_id": "00-1", "season": 2024, "week": 6, "opponent_team": "LAC",
             "targets": 6, "receptions": 4, "receiving_yards": 50, "receiving_tds": 0},
            # A different player, should never leak into "00-1"'s history.
            {"player_id": "00-2", "season": 2024, "week": 6, "opponent_team": "KC",
             "targets": 20, "receptions": 15, "receiving_yards": 300, "receiving_tds": 3},
        ]
    )


def test_games_played_counts_only_this_player_vs_this_opponent():
    history = build_player_history(_weekly_df(), "00-1", "Test WR", "WR", "KC")
    assert history.career_games == 4
    assert history.games_vs_opponent == 2


def test_ppg_delta_is_positive_when_matchup_outperforms_career():
    history = build_player_history(_weekly_df(), "00-1", "Test WR", "WR", "KC")
    # vs KC: receptions 8 & 6 (PPR pts higher) vs career average including two smaller games.
    assert history.ppg_delta is not None
    assert history.ppg_delta > 0


def test_stat_averages_use_position_specific_keys():
    history = build_player_history(_weekly_df(), "00-1", "Test WR", "WR", "KC")
    assert set(history.stat_averages_vs_opponent.keys()) == {
        "targets", "receptions", "receiving_yards", "receiving_tds"
    }
    assert history.stat_averages_vs_opponent["targets"] == 9.5  # (10+9)/2


def test_small_sample_flag():
    history = build_player_history(_weekly_df(), "00-1", "Test WR", "WR", "KC")
    assert history.small_sample is True  # 2 games < 3

    many_games = pd.concat([_weekly_df()] * 2, ignore_index=True)
    history_more = build_player_history(many_games, "00-1", "Test WR", "WR", "KC")
    assert history_more.small_sample is False  # 4 games >= 3


def test_no_history_vs_opponent_returns_none_ppg():
    history = build_player_history(_weekly_df(), "00-1", "Test WR", "WR", "SEA")
    assert history.games_vs_opponent == 0
    assert history.ppg_vs_opponent is None
    assert history.ppg_delta is None
    assert history.has_history is False


def test_team_alias_is_normalized_before_matching():
    # opponent given as the old/alternate abbreviation should still match "LV" rows.
    df = pd.DataFrame(
        [
            {"player_id": "00-1", "season": 2024, "week": 1, "opponent_team": "LV",
             "targets": 8, "receptions": 6, "receiving_yards": 80, "receiving_tds": 1},
        ]
    )
    history = build_player_history(df, "00-1", "Test WR", "WR", "OAK")
    assert history.games_vs_opponent == 1
