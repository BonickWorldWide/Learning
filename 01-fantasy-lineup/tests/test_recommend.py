from fantasy_lineup.models import (
    ContinuityFlags,
    PlayerMatchupHistory,
    PlayerReport,
    PlayerWeek,
    TeamMatchupTendency,
)
from fantasy_lineup.recommend import build_start_over_lines, group_by_position, rank_group

NO_TENDENCY = TeamMatchupTendency(
    team="OPP", opponent="X", games=0, seasons_considered=[], run_rate=None,
    pass_rate=None, avg_rush_yards=None, avg_pass_yards=None, avg_points_for=None,
)
NO_CONTINUITY_ISSUES = ContinuityFlags(
    team="OPP", current_coach="Coach", prior_coaches=["Coach"],
    current_qb="QB", prior_qbs=["QB"],
)


def make_report(name, position, ppg_delta, games_vs_opponent=5, tendency=NO_TENDENCY, continuity=NO_CONTINUITY_ISSUES):
    player = PlayerWeek(name=name, position=position, lineup_slot="BE", pro_team="X", pro_opponent="OPP")
    history = PlayerMatchupHistory(
        player_name=name, position=position, opponent="OPP",
        games_vs_opponent=games_vs_opponent, career_games=20,
        ppg_vs_opponent=12.0, career_ppg=12.0 - ppg_delta if ppg_delta is not None else None,
        ppg_delta=ppg_delta,
    )
    return PlayerReport(player=player, history=history, team_tendency=tendency, continuity=continuity)


def test_group_by_position_splits_correctly():
    reports = [make_report("RB A", "RB", 2.0), make_report("WR A", "WR", 1.0), make_report("RB B", "RB", -1.0)]
    groups = group_by_position(reports)
    assert set(groups.keys()) == {"RB", "WR"}
    assert len(groups["RB"]) == 2


def test_rank_group_orders_by_ppg_delta_descending():
    reports = [make_report("Low", "RB", -3.0), make_report("High", "RB", 5.0), make_report("Mid", "RB", 1.0)]
    ranked = rank_group(reports)
    assert [r.report.player.name for r in ranked] == ["High", "Mid", "Low"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_no_history_player_ranks_last():
    reports = [make_report("Has History", "RB", -2.0), make_report("No History", "RB", None, games_vs_opponent=0)]
    ranked = rank_group(reports)
    assert [r.report.player.name for r in ranked] == ["Has History", "No History"]


def test_summary_mentions_delta_and_game_count():
    ranked = rank_group([make_report("Player A", "RB", 4.5, games_vs_opponent=6)])
    assert "+4.5 pts/g" in ranked[0].summary
    assert "6g" in ranked[0].summary


def test_summary_flags_small_sample():
    ranked = rank_group([make_report("Player A", "RB", 4.5, games_vs_opponent=2)])
    assert "small sample: 2g" in ranked[0].summary


def test_summary_flags_qb_and_coach_changes():
    changed = ContinuityFlags(
        team="OPP", current_coach="New", prior_coaches=["Old"],
        current_qb="New QB", prior_qbs=["Old QB"],
    )
    ranked = rank_group([make_report("Player A", "RB", 4.5, continuity=changed)])
    assert "new HC since these games" in ranked[0].summary
    assert "different starting QB then" in ranked[0].summary


def test_tendency_clause_for_run_heavy_matchup():
    run_heavy = TeamMatchupTendency(
        team="MYTEAM", opponent="OPP", games=5, seasons_considered=[2023, 2024],
        run_rate=0.62, pass_rate=0.38, avg_rush_yards=140, avg_pass_yards=180, avg_points_for=27,
    )
    ranked = rank_group([make_report("RB A", "RB", 2.0, tendency=run_heavy)])
    assert "leans run (62%)" in ranked[0].summary


def test_tendency_clause_suppressed_for_small_sample():
    one_game_run_heavy = TeamMatchupTendency(
        team="MYTEAM", opponent="OPP", games=1, seasons_considered=[2024],
        run_rate=0.90, pass_rate=0.10, avg_rush_yards=200, avg_pass_yards=20, avg_points_for=30,
    )
    ranked = rank_group([make_report("RB A", "RB", 2.0, tendency=one_game_run_heavy)])
    assert "leans run" not in ranked[0].summary


def test_build_start_over_lines_pairs_consecutive_ranks():
    reports = [make_report("High", "RB", 5.0), make_report("Mid", "RB", 1.0), make_report("Low", "RB", -2.0)]
    ranked = rank_group(reports)
    lines = build_start_over_lines(ranked)
    assert lines == [
        "Start High over Mid: " + ranked[0].summary,
        "Start Mid over Low: " + ranked[1].summary,
    ]
