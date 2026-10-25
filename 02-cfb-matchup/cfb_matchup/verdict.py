from dataclasses import dataclass

from .models import ContinuityFlags, HeadToHeadSummary, SimulationResult, TeamRecentForm
from .simulate import moneyline_ev, moneyline_to_implied_prob

# A projected margin bigger than this counts as "a clear talent gap" in the
# factor list, rather than a close game the model just barely leans one way on.
CLEAR_GAP_SPREAD = 10.0

# How much bigger one team's recent scoring margin needs to be than the
# other's before it's called out as a driving factor.
NOTABLE_MARGIN_DIFFERENCE = 3.0

# How much tougher one team's recent schedule needs to have been, in average
# opponent point differential, before it's called out as a driving factor.
NOTABLE_SOS_DIFFERENCE = 5.0

# A cover/over probability within this much of 50% is called a toss-up
# rather than a lean -- the model and the real line are close enough that
# picking a side would be reading noise as a signal.
NO_LEAN_BAND = 0.05

# The minimum expected profit per $100 staked, at the real sportsbook price,
# before the straight-up fallback pick (see _spread_pick below) calls it a
# real value bet rather than just "the more likely winner." A real user's
# betting record showed exactly the gap this closes: 5-4 on moneyline
# favorites (mostly -120 to -750) that still lost money overall, because
# going 55% on heavy favorites isn't enough to clear what those prices
# demand. $0 is the breakeven point; this sits a little above it
# deliberately, since the model's own win probability is an estimate, not a
# certainty, and a bet that only clears zero by a hair is betting on the
# model being exactly right, not on having a real edge.
MIN_EV_FOR_VALUE_BET = 3.00


@dataclass
class Verdict:
    favorite: str
    underdog: str
    favorite_win_prob: float
    margin: float
    headline: str
    factors: list[str]
    confidence_notes: list[str]
    # None unless a real sportsbook line was typed in (see simulate_game's
    # vegas_spread/vegas_total) -- a plain-English pick, not just a number,
    # because "what should I actually bet" was the point of entering a line
    # at all.
    spread_pick: str | None = None
    total_pick: str | None = None


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
        spread_pick=_spread_pick(simulation),
        total_pick=_total_pick(simulation),
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


def format_spread_line(team_a: str, team_b: str, vegas_spread_for_a: float) -> str:
    """`vegas_spread_for_a` uses the model's own convention (positive =
    team_a favored) -- converted here into how a sportsbook actually shows
    it, favorite negative: "Ohio State -7.5 / Michigan +7.5"."""
    if vegas_spread_for_a > 0:
        favorite, underdog, points = team_a, team_b, vegas_spread_for_a
    elif vegas_spread_for_a < 0:
        favorite, underdog, points = team_b, team_a, -vegas_spread_for_a
    else:
        return f"{team_a}/{team_b} pick'em"
    return f"{favorite} -{points:.1f} / {underdog} +{points:.1f}"


def _spread_pick(simulation: SimulationResult) -> str | None:
    if simulation.vegas_spread is None:
        return None

    line_desc = format_spread_line(simulation.team_a, simulation.team_b, simulation.vegas_spread)
    prob = simulation.team_a_cover_prob
    edge = simulation.projected_spread - simulation.vegas_spread  # points, in team_a's favor

    if abs(prob - 0.5) < NO_LEAN_BAND:
        # The spread itself is a coin flip either way -- rather than a
        # vague "too close to call" with nothing to act on, fall back to
        # the one question the model still has a real opinion on: who
        # actually wins the game. This can -- and often will -- be a
        # different team than whichever side of the spread the model
        # barely favors, which is the whole point of surfacing it
        # explicitly rather than defaulting to the spread pick regardless.
        a_is_more_likely = simulation.team_a_win_prob >= simulation.team_b_win_prob
        win_favorite = simulation.team_a if a_is_more_likely else simulation.team_b
        win_prob = max(simulation.team_a_win_prob, simulation.team_b_win_prob)
        why = (
            f"the spread ({line_desc}) is too close to call (model gives it a {prob:.0%} cover probability "
            f"either way), so this falls back to who's actually more likely to win the game ({win_prob:.0%})"
        )

        moneyline = simulation.vegas_moneyline_a if a_is_more_likely else simulation.vegas_moneyline_b
        if moneyline is None:
            # No real "to win" price was typed in -- this can only say who's
            # more likely to win, not whether that team is worth betting on
            # at whatever price a book is actually offering. See
            # simulate.moneyline_ev: being right more often than not is not
            # the same as the price being worth paying.
            return (
                f"Pick {win_favorite} to win outright -- {why}. (No real moneyline price was given for "
                f"{win_favorite}, so this can't say whether that's actually worth betting at whatever odds "
                "a sportsbook is offering -- see --moneyline-a/--moneyline-b.)"
            )

        ev = moneyline_ev(win_prob, moneyline)
        implied = moneyline_to_implied_prob(moneyline)
        if ev >= MIN_EV_FOR_VALUE_BET:
            return (
                f"Pick {win_favorite} to win outright at {moneyline:+d} -- {why}, and at that price "
                f"(implying a {implied:.0%} win probability) this is real value: an expected "
                f"+${ev:.2f} per $100 staked, not just the more likely winner."
            )
        return (
            f"No bet, even though {win_favorite} is the more likely winner ({win_prob:.0%}) -- {why}, but at "
            f"{moneyline:+d} the market is already demanding a {implied:.0%} win probability to break even, "
            f"which doesn't leave real value (expected ${ev:+.2f} per $100 staked). This is exactly the "
            "trap a heavy favorite's price sets: being right more often than not doesn't cover what laying "
            "that much to win a little actually costs when it's wrong."
        )

    side = simulation.team_a if prob > 0.5 else simulation.team_b
    side_prob = prob if prob > 0.5 else 1 - prob
    return (
        f"Pick {side} against the spread ({line_desc}) based on covering in {side_prob:.0%} of simulated "
        f"trials (model's own projected spread is {simulation.projected_spread:+.1f}, {abs(edge):.1f} points "
        f"{'better for' if edge > 0 else 'worse for'} {simulation.team_a} than the actual line)."
    )


def _total_pick(simulation: SimulationResult) -> str | None:
    if simulation.vegas_total is None:
        return None

    prob = simulation.over_prob
    edge = simulation.projected_total - simulation.vegas_total

    if abs(prob - 0.5) < NO_LEAN_BAND:
        return (
            f"Too close to call on the total ({simulation.vegas_total:.1f}) -- the model's own projected "
            f"total ({simulation.projected_total:.1f}) is close enough to the actual line that neither "
            "side has a real edge. Unlike the spread, there's no separate question to fall back to here."
        )

    side = "Over" if prob > 0.5 else "Under"
    side_prob = prob if prob > 0.5 else 1 - prob
    return (
        f"Pick {side} {simulation.vegas_total:.1f} based on hitting in {side_prob:.0%} of simulated trials "
        f"(model's own projected total is {simulation.projected_total:.1f}, {abs(edge):.1f} points "
        f"{'higher' if edge > 0 else 'lower'} than the actual line)."
    )
