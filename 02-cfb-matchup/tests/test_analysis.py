from cfb_matchup.analysis import build_matchup_report
from cfb_matchup.models import Game


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
