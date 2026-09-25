import pandas as pd

from fantasy_lineup.models import PlayerWeek
from fantasy_lineup.report import build_player_reports


def _weekly_df():
    return pd.DataFrame(
        [
            {"player_id": "00-1", "player_name": "Known RB", "season": 2024, "week": 1, "opponent_team": "SEA",
             "recent_team": "SF", "position": "RB",
             "carries": 20, "rushing_yards": 90, "rushing_tds": 1, "targets": 3,
             "receptions": 2, "receiving_yards": 15, "receiving_tds": 0,
             "attempts": 0, "passing_yards": 0, "passing_tds": 0, "interceptions": 0},
        ]
    )


def _games_df():
    return pd.DataFrame(
        [
            {"season": 2024, "week": 1, "home_team": "SF", "away_team": "SEA",
             "home_score": 24.0, "away_score": 17.0,
             "home_coach": "Coach", "away_coach": "Other Coach",
             "home_qb_name": "Some QB", "away_qb_name": "Other QB"},
        ]
    )


def _players():
    return [
        PlayerWeek(name="Known RB", position="RB", lineup_slot="RB", pro_team="SF", pro_opponent="SEA", gsis_id="00-1"),
        PlayerWeek(name="Unknown QB", position="QB", lineup_slot="QB", pro_team="SF", pro_opponent="SEA", gsis_id=None),
        PlayerWeek(name="Some Kicker", position="K", lineup_slot="K", pro_team="SF", pro_opponent="SEA", gsis_id=None),
    ]


def test_kicker_is_excluded():
    reports = build_player_reports(
        _players(), _weekly_df(), _games_df(),
        current_season=2024, scoring="ppr", team_seasons=[2024],
    )
    names = [r.player.name for r in reports]
    assert "Some Kicker" not in names
    assert len(reports) == 2


def test_known_player_gets_real_history():
    reports = build_player_reports(
        _players(), _weekly_df(), _games_df(),
        current_season=2024, scoring="ppr", team_seasons=[2024],
    )
    rb_report = next(r for r in reports if r.player.name == "Known RB")
    assert rb_report.history.games_vs_opponent == 1
    assert rb_report.history.has_history is True


def test_unidentifiable_player_gets_empty_history_not_a_crash():
    reports = build_player_reports(
        _players(), _weekly_df(), _games_df(),
        current_season=2024, scoring="ppr", team_seasons=[2024],
    )
    qb_report = next(r for r in reports if r.player.name == "Unknown QB")
    assert qb_report.history.has_history is False
    assert qb_report.history.games_vs_opponent == 0


def test_team_tendency_is_shared_across_teammates():
    reports = build_player_reports(
        _players(), _weekly_df(), _games_df(),
        current_season=2024, scoring="ppr", team_seasons=[2024],
    )
    rb_report = next(r for r in reports if r.player.name == "Known RB")
    qb_report = next(r for r in reports if r.player.name == "Unknown QB")
    # Same team + same opponent -> computed once and reused, not recomputed per player.
    assert rb_report.team_tendency is qb_report.team_tendency
