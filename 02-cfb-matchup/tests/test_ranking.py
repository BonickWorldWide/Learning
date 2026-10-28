import pytest

from cfb_matchup.analysis import MatchupReport
from cfb_matchup.backtest import BREAK_EVEN_ATS_RATE
from cfb_matchup.continuity import build_continuity
from cfb_matchup.models import HeadToHeadSummary, PowerRating, RecordSplit, SimulationResult, TeamRecentForm
from cfb_matchup.ranking import game_edge, rank_games
from cfb_matchup.simulate import moneyline_to_implied_prob
from cfb_matchup.verdict import build_verdict


def make_sim(**overrides) -> SimulationResult:
    defaults = dict(
        team_a="Alpha", team_b="Beta", n_simulations=10_000,
        team_a_win_prob=0.6, team_b_win_prob=0.4,
        team_a_projected_score=28.0, team_b_projected_score=24.0,
        projected_spread=4.0, projected_total=52.0,
        team_a_moneyline=-150, team_b_moneyline=130,
    )
    defaults.update(overrides)
    return SimulationResult(**defaults)


def make_report(sim: SimulationResult) -> MatchupReport:
    h2h = HeadToHeadSummary(
        team_a="Alpha", team_b="Beta",
        all_time=RecordSplit("all-time", 6, 3, 3, 0, 5.0, 5.0),
        last_10=RecordSplit("l10", 6, 3, 3, 0, 5.0, 5.0),
        last_20=RecordSplit("l20", 6, 3, 3, 0, 5.0, 5.0),
    )
    form_a = TeamRecentForm(
        team="Alpha", seasons=[2024], games_played=12, wins=8, losses=4,
        points_for_per_game=27.0, points_against_per_game=24.0,
        home_record=(4, 2), away_record=(4, 2), strength_of_schedule=0.0,
    )
    form_b = TeamRecentForm(
        team="Beta", seasons=[2024], games_played=12, wins=8, losses=4,
        points_for_per_game=27.0, points_against_per_game=24.0,
        home_record=(4, 2), away_record=(4, 2), strength_of_schedule=0.0,
    )
    rating_a = PowerRating(team="Alpha", rating=5.0, expected_points=28.0)
    rating_b = PowerRating(team="Beta", rating=3.0, expected_points=24.0)
    verdict = build_verdict(sim, h2h, form_a, form_b, build_continuity("Alpha"), build_continuity("Beta"))
    return MatchupReport(
        h2h=h2h, form_a=form_a, form_b=form_b, common_opponent_results=[],
        rating_a=rating_a, rating_b=rating_b, simulation=sim, verdict=verdict,
    )


def test_game_edge_for_a_real_ats_lean_matches_hand_calc():
    sim = make_sim(vegas_spread=2.0, team_a_cover_prob=0.65, team_b_cover_prob=0.35)
    report = make_report(sim)
    assert game_edge(report) == pytest.approx(0.65 - BREAK_EVEN_ATS_RATE)


def test_game_edge_takes_the_stronger_side_whichever_team_it_is():
    # Team_b is the one actually covering more often here.
    sim = make_sim(vegas_spread=2.0, team_a_cover_prob=0.3, team_b_cover_prob=0.7)
    report = make_report(sim)
    assert game_edge(report) == pytest.approx(0.7 - BREAK_EVEN_ATS_RATE)


def test_game_edge_falls_back_to_moneyline_when_spread_is_a_coin_flip():
    sim = make_sim(
        vegas_spread=5.0, team_a_cover_prob=0.5, team_b_cover_prob=0.5,
        vegas_moneyline_a=-230,
    )
    report = make_report(sim)
    expected = 0.6 - moneyline_to_implied_prob(-230)
    assert game_edge(report) == pytest.approx(expected)


def test_game_edge_fallback_can_be_negative_when_the_price_is_bad():
    # Model likes Alpha at 60%, but -400 demands 80% -- a real, negative
    # edge, not just "no pick." This must rank BELOW a neutral 0.0 game,
    # not be floored at zero, since it's actively a worse bet than no bet.
    sim = make_sim(
        vegas_spread=5.0, team_a_cover_prob=0.5, team_b_cover_prob=0.5,
        vegas_moneyline_a=-400,
    )
    report = make_report(sim)
    assert game_edge(report) < 0


def test_game_edge_zero_when_spread_is_a_coin_flip_and_no_moneyline_given():
    sim = make_sim(vegas_spread=5.0, team_a_cover_prob=0.5, team_b_cover_prob=0.5)
    report = make_report(sim)
    assert game_edge(report) == 0.0


def test_game_edge_zero_when_no_spread_was_given_at_all():
    sim = make_sim()  # vegas_spread defaults to None
    report = make_report(sim)
    assert game_edge(report) == 0.0


def test_rank_games_orders_by_edge_highest_first():
    strong = make_report(make_sim(vegas_spread=2.0, team_a_cover_prob=0.70, team_b_cover_prob=0.30))
    weak = make_report(make_sim(vegas_spread=2.0, team_a_cover_prob=0.58, team_b_cover_prob=0.42))
    none_ = make_report(make_sim())
    ranked = rank_games([weak, none_, strong], top_n=3)
    assert ranked == [strong, weak, none_]


def test_rank_games_truncates_to_top_n():
    reports = [
        make_report(make_sim(vegas_spread=2.0, team_a_cover_prob=p, team_b_cover_prob=1 - p))
        for p in (0.60, 0.65, 0.70, 0.75)
    ]
    best_two = rank_games(reports, top_n=2)
    assert len(best_two) == 2
    assert game_edge(best_two[0]) >= game_edge(best_two[1]) >= max(game_edge(r) for r in reports[:2])


def test_rank_games_top_n_larger_than_the_list_returns_everything():
    reports = [make_report(make_sim())]
    assert rank_games(reports, top_n=8) == reports
