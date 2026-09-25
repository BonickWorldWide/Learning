from dataclasses import dataclass

from .models import ContinuityFlags, HeadToHeadSummary, SimulationResult, TeamRecentForm

# A projected margin bigger than this counts as "a clear talent gap" in the
# factor list, rather than a close game the model just barely leans one way on.
CLEAR_GAP_SPREAD = 10.0

# How much bigger one team's recent scoring margin needs to be than the
# other's before it's called out as a driving factor.
NOTABLE_MARGIN_DIFFERENCE = 3.0

# How much tougher one team's recent schedule needs to have been, in average
# opponent point differential, before it's called out as a driving factor.
NOTABLE_SOS_DIFFERENCE = 5.0


@dataclass
class Verdict:
    favorite: str
    underdog: str
    favorite_win_prob: float
    margin: float
    headline: str
    factors: list[str]
    confidence_notes: list[str]


def build_verdict(
    simulation: SimulationResult,
    h2h: HeadToHeadSummary,
    team_a_form: TeamRecentForm,
    team_b_form: TeamRecentForm,
    team_a_continuity: ContinuityFlags,
    team_b_continuity: ContinuityFlags,
) -> Verdict:
    if simulation.team_a_win_prob >= simulation.team_b_win_prob:
        favorite, underdog = simulation.team_a, simulation.team_b
        favorite_prob = simulation.team_a_win_prob
        margin = simulation.projected_spread
    else:
        favorite, underdog = simulation.team_b, simulation.team_a
        favorite_prob = simulation.team_b_win_prob
        margin = -simulation.projected_spread

    headline = f"{favorite} favored by {margin:.1f}, {favorite_prob:.0%} win probability"

    return Verdict(
        favorite=favorite,
        underdog=underdog,
        favorite_win_prob=favorite_prob,
        margin=margin,
        headline=headline,
        factors=_top_factors(simulation, h2h, team_a_form, team_b_form),
        confidence_notes=_confidence_notes(h2h, team_a_continuity, team_b_continuity),
    )


def _top_factors(
    simulation: SimulationResult,
    h2h: HeadToHeadSummary,
    team_a_form: TeamRecentForm,
    team_b_form: TeamRecentForm,
) -> list[str]:
    factors = []

    a_margin = _scoring_margin(team_a_form)
    b_margin = _scoring_margin(team_b_form)
    if a_margin is not None and b_margin is not None and abs(a_margin - b_margin) > NOTABLE_MARGIN_DIFFERENCE:
        better = team_a_form.team if a_margin > b_margin else team_b_form.team
        factors.append(f"{better} has the stronger recent scoring margin ({a_margin:+.1f} vs {b_margin:+.1f} pts/g)")

    at = h2h.all_time
    if at.games >= 5:
        if at.team_a_wins >= 3 and at.team_a_wins > at.team_b_wins * 1.5:
            factors.append(f"{h2h.team_a} has historically dominated this series ({at.team_a_wins}-{at.team_b_wins})")
        elif at.team_b_wins >= 3 and at.team_b_wins > at.team_a_wins * 1.5:
            factors.append(f"{h2h.team_b} has historically dominated this series ({at.team_b_wins}-{at.team_a_wins})")

    if abs(simulation.projected_spread) > CLEAR_GAP_SPREAD:
        leader = simulation.team_a if simulation.projected_spread > 0 else simulation.team_b
        factors.append(f"the model sees a clear talent gap favoring {leader}")

    a_sos, b_sos = team_a_form.strength_of_schedule, team_b_form.strength_of_schedule
    if a_sos is not None and b_sos is not None and abs(a_sos - b_sos) > NOTABLE_SOS_DIFFERENCE:
        tougher = team_a_form.team if a_sos > b_sos else team_b_form.team
        factors.append(f"{tougher} has played a tougher recent schedule")

    return factors[:3]


def _confidence_notes(
    h2h: HeadToHeadSummary, team_a_continuity: ContinuityFlags, team_b_continuity: ContinuityFlags
) -> list[str]:
    notes = []

    if h2h.rarely_play:
        notes.append(
            f"{h2h.team_a} and {h2h.team_b} have only played {h2h.all_time.games} time(s) -- "
            "the head-to-head history here is close to meaningless."
        )
    elif h2h.small_sample:
        notes.append(f"Only {h2h.all_time.games} meetings all-time -- weigh the head-to-head trends lightly.")

    for continuity in (team_a_continuity, team_b_continuity):
        if continuity.has_flags:
            notes.append(f"{continuity.team}: {'; '.join(continuity.notes)}")

    return notes


def _scoring_margin(form: TeamRecentForm) -> float | None:
    if form.points_for_per_game is None or form.points_against_per_game is None:
        return None
    return form.points_for_per_game - form.points_against_per_game
