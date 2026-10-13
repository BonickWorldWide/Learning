import math

import pytest

from cfb_matchup.backtest import (
    BREAK_EVEN_ATS_RATE,
    BacktestGame,
    ats_accuracy,
    ats_graded_games,
    brier_score,
    mean_abs_spread_error,
    mean_abs_total_error,
    over_under_accuracy,
    over_under_graded_games,
    run_backtest,
    win_accuracy,
)
from cfb_matchup.models import BettingLine, Game


def make_result(team_a_won, predicted_win_prob_a, predicted_spread=0.0, predicted_total=50.0,
                 actual_score_a=None, actual_score_b=None,
                 vegas_spread=None, vegas_total=None, team_a_cover_prob=None, over_prob=None):
    if actual_score_a is None or actual_score_b is None:
        actual_score_a, actual_score_b = (30, 10) if team_a_won else (10, 30)
    return BacktestGame(
        season=2024, week=1, team_a="A", team_b="B",
        predicted_win_prob_a=predicted_win_prob_a,
        predicted_spread=predicted_spread, predicted_total=predicted_total,
        actual_score_a=actual_score_a, actual_score_b=actual_score_b,
        vegas_spread=vegas_spread, vegas_total=vegas_total,
        team_a_cover_prob=team_a_cover_prob, over_prob=over_prob,
    )


def test_actual_margin_and_total():
    r = make_result(True, 0.7, actual_score_a=35, actual_score_b=20)
    assert r.actual_margin == 15
    assert r.actual_total == 55
    assert r.team_a_won is True


def test_favorite_won_when_team_a_favored_and_wins():
    assert make_result(True, 0.65).favorite_won is True


def test_favorite_won_false_when_team_a_favored_but_loses():
    assert make_result(False, 0.65).favorite_won is False


def test_favorite_won_when_team_b_favored_and_team_a_loses():
    # prob_a < 0.5 means team B is favored; team A actually losing is a correct call.
    assert make_result(False, 0.35).favorite_won is True


def test_brier_score_perfect_predictions_is_zero():
    results = [make_result(True, 1.0), make_result(False, 0.0)]
    assert brier_score(results) == pytest.approx(0.0)


def test_brier_score_coin_flip_guesses_is_quarter():
    results = [make_result(True, 0.5), make_result(False, 0.5)]
    assert brier_score(results) == pytest.approx(0.25)


def test_brier_score_worst_case_is_one():
    results = [make_result(True, 0.0), make_result(False, 1.0)]
    assert brier_score(results) == pytest.approx(1.0)


def test_win_accuracy():
    results = [make_result(True, 0.7), make_result(False, 0.7), make_result(True, 0.3)]
    # g1: favored A wins -> correct. g2: favored A, A lost -> wrong. g3: favored B, A won -> wrong.
    assert win_accuracy(results) == pytest.approx(1 / 3)


def test_mean_abs_spread_error():
    results = [
        make_result(True, 0.6, predicted_spread=10.0, actual_score_a=30, actual_score_b=24),  # margin 6, error 4
        make_result(True, 0.6, predicted_spread=-5.0, actual_score_a=20, actual_score_b=10),  # margin 10, error 15
    ]
    assert mean_abs_spread_error(results) == pytest.approx((4 + 15) / 2)


def test_mean_abs_total_error():
    results = [
        make_result(True, 0.6, predicted_total=50.0, actual_score_a=30, actual_score_b=24),  # total 54, error 4
        make_result(True, 0.6, predicted_total=40.0, actual_score_a=20, actual_score_b=10),  # total 30, error 10
    ]
    assert mean_abs_total_error(results) == pytest.approx((4 + 10) / 2)


def test_empty_results_return_nan_not_a_crash():
    assert math.isnan(brier_score([]))
    assert math.isnan(win_accuracy([]))
    assert math.isnan(mean_abs_spread_error([]))
    assert math.isnan(mean_abs_total_error([]))


def _game(season, week, home, away, home_score, away_score):
    return Game(season, week, f"{season}-W{week}", home, away, home_score, away_score)


def test_run_backtest_skips_games_with_no_prior_history():
    games = [_game(2024, 1, "A", "B", 30, 10)]
    results = run_backtest(games, seasons_to_test=[2024], n_simulations=200)
    assert results == []


def test_run_backtest_predicts_later_games_using_earlier_ones():
    games = [
        _game(2024, 1, "A", "C", 30, 10),
        _game(2024, 1, "B", "D", 28, 14),
        _game(2024, 2, "A", "B", 35, 20),
    ]
    results = run_backtest(games, seasons_to_test=[2024], n_simulations=200)
    assert len(results) == 1
    r = results[0]
    assert (r.team_a, r.team_b) == ("A", "B")
    assert (r.actual_score_a, r.actual_score_b) == (35, 20)
    assert 0.0 <= r.predicted_win_prob_a <= 1.0


def test_run_backtest_only_targets_requested_seasons():
    games = [
        _game(2023, 1, "A", "C", 30, 10),
        _game(2024, 1, "A", "B", 35, 20),
        _game(2024, 2, "A", "B", 21, 14),
    ]
    results = run_backtest(games, seasons_to_test=[2024], n_simulations=200)
    assert all(r.season == 2024 for r in results)
    assert len(results) == 2


# --- Grading against a real closing line, not just who won ---


def test_break_even_ats_rate_matches_standard_vig_math():
    # A standard -110/-110 line: bet $110 to win $100. Break-even win rate
    # is risk / (risk + win) = 110 / 210.
    assert BREAK_EVEN_ATS_RATE == pytest.approx(110 / 210)


def test_team_a_covered_true_when_margin_beats_the_line():
    r = make_result(True, 0.6, actual_score_a=30, actual_score_b=20, vegas_spread=7.0)  # margin 10 > 7
    assert r.team_a_covered is True


def test_team_a_covered_false_when_margin_falls_short_of_the_line():
    r = make_result(True, 0.6, actual_score_a=24, actual_score_b=20, vegas_spread=7.0)  # margin 4 < 7
    assert r.team_a_covered is False


def test_team_a_covered_none_on_an_exact_push():
    r = make_result(True, 0.6, actual_score_a=27, actual_score_b=20, vegas_spread=7.0)  # margin exactly 7
    assert r.team_a_covered is None


def test_team_a_covered_none_with_no_line_at_all():
    r = make_result(True, 0.6, actual_score_a=30, actual_score_b=20)
    assert r.team_a_covered is None


def test_went_over_and_push_behave_the_same_way_as_covered():
    assert make_result(True, 0.6, actual_score_a=30, actual_score_b=25, vegas_total=50.0).went_over is True
    assert make_result(True, 0.6, actual_score_a=20, actual_score_b=20, vegas_total=50.0).went_over is False
    assert make_result(True, 0.6, actual_score_a=25, actual_score_b=25, vegas_total=50.0).went_over is None


def test_model_ats_pick_is_none_without_a_line_or_without_a_real_lean():
    assert make_result(True, 0.6).model_ats_pick is None  # no line at all
    assert make_result(True, 0.6, vegas_spread=5.0, team_a_cover_prob=0.51).model_ats_pick is None  # too close


def test_model_ats_pick_names_the_team_the_model_actually_leans_toward():
    picks_a = make_result(True, 0.6, vegas_spread=5.0, team_a_cover_prob=0.65)
    picks_b = make_result(True, 0.6, vegas_spread=5.0, team_a_cover_prob=0.35)
    assert picks_a.model_ats_pick == "A"
    assert picks_b.model_ats_pick == "B"


def test_model_total_pick_names_a_real_side_or_none():
    assert make_result(True, 0.6).model_total_pick is None
    assert make_result(True, 0.6, vegas_total=50.0, over_prob=0.51).model_total_pick is None  # too close
    assert make_result(True, 0.6, vegas_total=50.0, over_prob=0.7).model_total_pick == "over"
    assert make_result(True, 0.6, vegas_total=50.0, over_prob=0.3).model_total_pick == "under"


def test_ats_pick_won_matches_whether_the_picked_side_actually_covered():
    # Model picks A (65% cover prob), A actually covers.
    won = make_result(
        True, 0.6, actual_score_a=30, actual_score_b=20, vegas_spread=5.0, team_a_cover_prob=0.65,
    )
    assert won.ats_pick_won is True

    # Model picks A, but B actually covers.
    lost = make_result(
        True, 0.6, actual_score_a=22, actual_score_b=20, vegas_spread=5.0, team_a_cover_prob=0.65,
    )
    assert lost.ats_pick_won is False


def test_ats_pick_won_none_without_a_real_pick_or_on_a_push():
    assert make_result(True, 0.6).ats_pick_won is None  # no line
    no_lean = make_result(True, 0.6, actual_score_a=30, actual_score_b=20, vegas_spread=5.0, team_a_cover_prob=0.51)
    assert no_lean.ats_pick_won is None
    push = make_result(True, 0.6, actual_score_a=25, actual_score_b=20, vegas_spread=5.0, team_a_cover_prob=0.65)
    assert push.ats_pick_won is None


def test_ats_accuracy_only_counts_graded_games():
    results = [
        make_result(True, 0.6, actual_score_a=30, actual_score_b=20, vegas_spread=5.0, team_a_cover_prob=0.65),  # won
        make_result(True, 0.6, actual_score_a=22, actual_score_b=20, vegas_spread=5.0, team_a_cover_prob=0.65),  # lost
        make_result(True, 0.6),  # no line at all -- must not count toward the denominator
    ]
    assert len(ats_graded_games(results)) == 2
    assert ats_accuracy(results) == pytest.approx(0.5)


def test_over_under_accuracy_only_counts_graded_games():
    results = [
        make_result(True, 0.6, actual_score_a=30, actual_score_b=25, vegas_total=50.0, over_prob=0.7),  # over, won
        make_result(True, 0.6, actual_score_a=20, actual_score_b=20, vegas_total=50.0, over_prob=0.7),  # under, lost
        make_result(True, 0.6),  # no line
    ]
    assert len(over_under_graded_games(results)) == 2
    assert over_under_accuracy(results) == pytest.approx(0.5)


def test_ats_and_over_under_accuracy_nan_on_no_graded_games():
    results = [make_result(True, 0.6)]  # no line anywhere
    assert math.isnan(ats_accuracy(results))
    assert math.isnan(over_under_accuracy(results))


def test_run_backtest_wires_a_matching_line_into_the_result():
    games = [
        _game(2024, 1, "A", "C", 30, 10),
        _game(2024, 1, "B", "D", 28, 14),
        _game(2024, 2, "A", "B", 35, 20),
    ]
    lines = [BettingLine(season=2024, week=2, home_team="A", away_team="B", spread=-3.0, over_under=45.0)]
    results = run_backtest(games, seasons_to_test=[2024], n_simulations=500, lines=lines)
    assert len(results) == 1
    r = results[0]
    # CFBD's spread (-3.0, home favored by 3) becomes this codebase's
    # convention (positive = team_a/home favored): +3.0.
    assert r.vegas_spread == pytest.approx(3.0)
    assert r.vegas_total == pytest.approx(45.0)
    assert r.team_a_cover_prob is not None
    assert r.over_prob is not None


def test_run_backtest_leaves_line_fields_none_when_nothing_matches():
    games = [
        _game(2024, 1, "A", "C", 30, 10),
        _game(2024, 1, "B", "D", 28, 14),
        _game(2024, 2, "A", "B", 35, 20),
    ]
    # A line for a completely different game -- shouldn't match anything.
    lines = [BettingLine(season=2024, week=1, home_team="X", away_team="Y", spread=-3.0, over_under=45.0)]
    results = run_backtest(games, seasons_to_test=[2024], n_simulations=200, lines=lines)
    assert results[0].vegas_spread is None
    assert results[0].team_a_cover_prob is None
