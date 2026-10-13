import pytest

from cfb_matchup.analysis import build_matchup_report
from cfb_matchup.models import Game
from cfb_matchup.simulate import HOME_FIELD_ADVANTAGE


def _h2h_games():
    return [
        Game(2018, 1, "2018-09-01", "Alpha", "Beta", 30, 20),
        Game(2019, 1, "2019-09-01", "Beta", "Alpha", 24, 21),
        Game(2020, 1, "2020-09-01", "Alpha", "Beta", 35, 14),
        Game(2021, 1, "2021-09-01", "Beta", "Alpha", 27, 28),
        Game(2022, 1, "2022-09-01", "Alpha", "Beta", 17, 20, neutral_site=True),
        Game(2023, 1, "2023-09-01", "Alpha", "Beta", 40, 10),
        Game(2024, 1, "2024-09-01", "Beta", "Alpha", 21, 21),
    ]


def _recent_games():
    return [
        Game(2024, 1, "2024-09-01", "Alpha", "Common1", 35, 14),
        Game(2024, 2, "2024-09-08", "Common2", "Alpha", 24, 20),
        Game(2024, 3, "2024-09-15", "Alpha", "OnlyAlphaOpp", 40, 10),
        Game(2024, 1, "2024-09-01", "Beta", "Common1", 28, 21),
        Game(2024, 2, "2024-09-08", "Common2", "Beta", 10, 17),
        Game(2024, 3, "2024-09-15", "Beta", "OnlyBetaOpp", 45, 7),
        Game(2024, 4, "2024-09-22", "RandomOpp", "Common1", 30, 10),
    ]


def _build_report(**overrides):
    kwargs = dict(
        h2h_games=_h2h_games(),
        recent_games=_recent_games(),
        team_a="Alpha",
        team_b="Beta",
        recent_seasons=[2024],
        n_simulations=2_000,
        home_team="Alpha",
        neutral_site=False,
    )
    kwargs.update(overrides)
    return build_matchup_report(**kwargs)


def test_full_report_builds_without_error_and_all_sections_present():
    report = _build_report()
    assert report.h2h.all_time.games == 7
    assert report.form_a.team == "Alpha"
    assert report.form_b.team == "Beta"
    assert report.rating_a.team == "Alpha"
    assert report.simulation.team_a == "Alpha"
    assert report.verdict.favorite in ("Alpha", "Beta")


def test_common_opponents_flow_through_to_the_report():
    report = _build_report()
    opponents = {r.opponent for r in report.common_opponent_results}
    assert opponents == {"Common1", "Common2"}


def test_win_probabilities_are_a_valid_distribution():
    report = _build_report()
    sim = report.simulation
    assert 0.0 <= sim.team_a_win_prob <= 1.0
    assert sim.team_a_win_prob + sim.team_b_win_prob == 1.0


def test_sp_plus_rating_shifts_the_power_rating_when_supplied():
    without_sp = _build_report()
    with_sp = _build_report(sp_rating_a=25.0)
    assert with_sp.rating_a.rating != without_sp.rating_a.rating
    assert "external_rating" in with_sp.rating_a.components


def test_continuity_notes_propagate_into_the_verdict():
    report = _build_report(notes_a=["New offensive coordinator"])
    assert any("New offensive coordinator" in note for note in report.verdict.confidence_notes)


def test_rare_matchup_flags_low_confidence():
    # Two teams with a single meeting -- should show up as a confidence flag.
    sparse_h2h = [Game(2023, 1, "2023-09-01", "Alpha", "Beta", 24, 21)]
    report = _build_report(h2h_games=sparse_h2h)
    assert report.h2h.rarely_play is True
    assert any("meaningless" in note for note in report.verdict.confidence_notes)


def test_pace_data_shifts_the_power_rating_when_supplied():
    without_pace = _build_report()
    with_slow_pace = _build_report(plays_per_game_a=60.0)
    assert with_slow_pace.rating_a.rating != without_pace.rating_a.rating
    assert "pace_factor" in with_slow_pace.rating_a.components


def test_two_slow_tempo_teams_produce_a_lower_projected_total():
    # Same ratings either way (no plays_per_game in build_power_rating's own
    # components), but the actual game pace factor should scale both teams'
    # expected points down, and the total down with them.
    normal_pace = _build_report()
    both_slow = _build_report(plays_per_game_a=55.0, plays_per_game_b=55.0)
    assert both_slow.simulation.projected_total < normal_pace.simulation.projected_total


def test_returning_production_shifts_the_power_rating_when_supplied():
    without_rp = _build_report()
    with_high_rp = _build_report(returning_production_a=0.90)
    assert with_high_rp.rating_a.rating != without_rp.rating_a.rating
    assert "returning_production_adjustment" in with_high_rp.rating_a.components


def test_home_field_edge_uses_team_specific_split_once_theres_enough_sample():
    # Alpha: home margins +10 x3 (avg 10), away margins +4 x3 (avg 4) ->
    # edge (10 - 4) / 2 = 3.0, clearly different from the flat 2.5 default.
    # Beta only gets one game, nowhere near enough to clear its own
    # fallback threshold, so it should still show the flat default.
    games = [
        Game(2024, 1, "2024-09-01", "Alpha", "Opp1", 30, 20),
        Game(2024, 2, "2024-09-08", "Alpha", "Opp2", 30, 20),
        Game(2024, 3, "2024-09-15", "Alpha", "Opp3", 30, 20),
        Game(2024, 4, "2024-09-22", "Opp4", "Alpha", 20, 24),
        Game(2024, 5, "2024-09-29", "Opp5", "Alpha", 20, 24),
        Game(2024, 6, "2024-10-06", "Opp6", "Alpha", 20, 24),
        Game(2024, 7, "2024-10-13", "Beta", "OppB", 21, 14),
    ]
    report = build_matchup_report(
        h2h_games=[], recent_games=games, team_a="Alpha", team_b="Beta",
        recent_seasons=[2024], n_simulations=1_000, home_team="Alpha", neutral_site=False,
    )
    assert report.simulation.team_a_home_edge == pytest.approx(3.0)
    assert report.simulation.team_b_home_edge == HOME_FIELD_ADVANTAGE
