from .analysis import MatchupReport
from .backtest import BREAK_EVEN_ATS_RATE
from .simulate import moneyline_to_implied_prob
from .verdict import NO_LEAN_BAND

# "Should we have it to where I put in 8 games and it picks the top 4?"
# This answers that: one explainable number per game (its best available
# bet's edge over what that bet's price demands), highest first. Not an
# opaque blend of spread/total/moneyline signals that aren't directly
# comparable in the first place -- the same "one clear ranking signal"
# shape as discover.shortlist / screener.rank_pop_candidates in the
# sibling options-screener project.


def game_edge(report: MatchupReport) -> float:
    """How good the single best bet in this game is, as a probability
    edge over breakeven -- NOT a dollar EV, since a spread/total leg
    (assumed standard -110, because no spread-odds input is asked for)
    and a real-priced moneyline leg aren't comparable in dollars without
    assuming the exact same stake and price for every game.

    Mirrors verdict._spread_pick's own branching exactly, so a game's
    rank here always lines up with what its own printed pick says:

    - A real ATS lean (cover probability clears NO_LEAN_BAND away from
      50%) -- edge is that side's probability minus BREAK_EVEN_ATS_RATE
      (~52.4%, the standard -110 bar).
    - A coin-flip spread that falls back to the straight-up winner --
      edge is the win probability minus what the real moneyline price
      implies, same as simulate.moneyline_ev's question, but only when a
      real moneyline was actually typed in for that game.
    - Anything else (no spread given at all, a coin-flip spread with no
      moneyline either) -- 0.0. Not an error: a game with no real lean
      still ranks, just last, rather than being silently dropped or
      crashing a slate of 8 because one game had thinner input than the
      rest.
    """
    sim = report.simulation
    if sim.vegas_spread is None:
        return 0.0

    prob = sim.team_a_cover_prob
    if prob is None:
        return 0.0

    if abs(prob - 0.5) >= NO_LEAN_BAND:
        side_prob = max(prob, 1 - prob)
        return side_prob - BREAK_EVEN_ATS_RATE

    a_is_more_likely = sim.team_a_win_prob >= sim.team_b_win_prob
    win_prob = max(sim.team_a_win_prob, sim.team_b_win_prob)
    moneyline = sim.vegas_moneyline_a if a_is_more_likely else sim.vegas_moneyline_b
    if moneyline is None:
        return 0.0
    return win_prob - moneyline_to_implied_prob(moneyline)


def rank_games(reports: list[MatchupReport], top_n: int) -> list[MatchupReport]:
    """Every report's own game_edge, highest first, truncated to top_n."""
    return sorted(reports, key=game_edge, reverse=True)[:top_n]
