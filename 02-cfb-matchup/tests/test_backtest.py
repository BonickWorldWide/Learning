import math

import pytest

from cfb_matchup.backtest import (
    BacktestGame,
    brier_score,
    mean_abs_spread_error,
    mean_abs_total_error,
    run_backtest,
    win_accuracy,
)
from cfb_matchup.models import Game


def make_result(team_a_won, predicted_win_prob_a, predicted_spread=0.0, predicted_total=50.0,
                 actual_score_a=None, actual_score_b=None):
    if actual_score_a is None or actual_score_b is None:
        actual_score_a, actual_score_b = (30, 10) if team_a_won else (10, 30)
    return BacktestGame(
        season=2024, week=1, team_a="A", team_b="B",
        predicted_win_prob_a=predicted_win_prob_a,
        predicted_spread=predicted_spread, predicted_total=predicted_total,
        actual_score_a=actual_score_a, actual_score_b=actual_score_b,
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
