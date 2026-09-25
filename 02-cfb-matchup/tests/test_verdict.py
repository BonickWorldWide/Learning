from cfb_matchup.continuity import build_continuity
from cfb_matchup.models import HeadToHeadSummary, RecordSplit, SimulationResult, TeamRecentForm
from cfb_matchup.verdict import build_verdict

NO_CONTINUITY_A = build_continuity("Alpha")
NO_CONTINUITY_B = build_continuity("Beta")


def make_simulation(a_prob=0.6, spread=5.0) -> SimulationResult:
    return SimulationResult(
        team_a="Alpha", team_b="Beta", n_simulations=10_000,
        team_a_win_prob=a_prob, team_b_win_prob=1 - a_prob,
        team_a_projected_score=28.0, team_b_projected_score=28.0 - spread,
        projected_spread=spread, projected_total=56.0 - spread,
        team_a_moneyline=-150, team_b_moneyline=130,
    )


def make_h2h(games=6, a_wins=3, b_wins=3) -> HeadToHeadSummary:
    split = RecordSplit("all-time", games, a_wins, b_wins, 0, 5.0, 5.0)
    return HeadToHeadSummary(
        team_a="Alpha", team_b="Beta",
        all_time=split, last_10=split, last_20=split,
    )


def make_form(team, pf=27.0, pa=24.0, sos=0.0) -> TeamRecentForm:
    return TeamRecentForm(
        team=team, seasons=[2024], games_played=12, wins=8, losses=4,
        points_for_per_game=pf, points_against_per_game=pa,
        home_record=(4, 2), away_record=(4, 2), strength_of_schedule=sos,
    )


def test_favorite_is_whichever_team_has_higher_win_prob():
    verdict = build_verdict(
        make_simulation(a_prob=0.7, spread=8.0), make_h2h(),
        make_form("Alpha"), make_form("Beta"), NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert verdict.favorite == "Alpha"
    assert verdict.underdog == "Beta"
    assert verdict.margin == 8.0


def test_favorite_flips_to_team_b_when_team_b_has_higher_win_prob():
    verdict = build_verdict(
        make_simulation(a_prob=0.3, spread=-8.0), make_h2h(),
        make_form("Alpha"), make_form("Beta"), NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert verdict.favorite == "Beta"
    assert verdict.margin == 8.0  # always reported as a positive number


def test_scoring_margin_factor_triggers_on_notable_difference():
    verdict = build_verdict(
        make_simulation(), make_h2h(),
        make_form("Alpha", pf=30, pa=20),  # margin +10
        make_form("Beta", pf=24, pa=24),   # margin 0
        NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert any("stronger recent scoring margin" in f and "Alpha" in f for f in verdict.factors)


def test_scoring_margin_factor_does_not_trigger_on_small_difference():
    verdict = build_verdict(
        make_simulation(), make_h2h(),
        make_form("Alpha", pf=26, pa=24),  # margin +2
        make_form("Beta", pf=25, pa=24),   # margin +1, diff 1 < threshold
        NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert not any("scoring margin" in f for f in verdict.factors)


def test_historical_dominance_factor():
    verdict = build_verdict(
        make_simulation(), make_h2h(games=6, a_wins=5, b_wins=1),
        make_form("Alpha"), make_form("Beta"), NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert any("historically dominated" in f and "Alpha" in f for f in verdict.factors)


def test_clear_talent_gap_factor():
    verdict = build_verdict(
        make_simulation(a_prob=0.9, spread=15.0), make_h2h(),
        make_form("Alpha"), make_form("Beta"), NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert any("clear talent gap" in f and "Alpha" in f for f in verdict.factors)


def test_factors_capped_at_three():
    verdict = build_verdict(
        make_simulation(a_prob=0.9, spread=15.0),
        make_h2h(games=6, a_wins=5, b_wins=1),
        make_form("Alpha", pf=40, pa=10, sos=12.0),
        make_form("Beta", pf=20, pa=30, sos=-2.0),
        NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert len(verdict.factors) <= 3


def test_rarely_play_confidence_note():
    verdict = build_verdict(
        make_simulation(), make_h2h(games=2, a_wins=1, b_wins=1),
        make_form("Alpha"), make_form("Beta"), NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert any("close to meaningless" in n for n in verdict.confidence_notes)


def test_small_but_not_rare_sample_gets_lighter_note():
    verdict = build_verdict(
        make_simulation(), make_h2h(games=4, a_wins=2, b_wins=2),
        make_form("Alpha"), make_form("Beta"), NO_CONTINUITY_A, NO_CONTINUITY_B,
    )
    assert any("weigh the head-to-head trends lightly" in n for n in verdict.confidence_notes)
    assert not any("close to meaningless" in n for n in verdict.confidence_notes)


def test_continuity_notes_are_surfaced():
    flagged = build_continuity("Alpha", notes=["New head coach this season"])
    verdict = build_verdict(
        make_simulation(), make_h2h(),
        make_form("Alpha"), make_form("Beta"), flagged, NO_CONTINUITY_B,
    )
    assert any("New head coach this season" in n for n in verdict.confidence_notes)
