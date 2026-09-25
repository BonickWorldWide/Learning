from dataclasses import dataclass

from .continuity import build_continuity
from .h2h import build_head_to_head
from .models import (
    CommonOpponentResult,
    Game,
    HeadToHeadSummary,
    PowerRating,
    SimulationResult,
    TeamRecentForm,
)
from .power_rating import build_power_rating
from .recent_form import build_recent_form, common_opponents, scoring_std_dev
from .simulate import simulate_game
from .verdict import Verdict, build_verdict


@dataclass
class MatchupReport:
    h2h: HeadToHeadSummary
    form_a: TeamRecentForm
    form_b: TeamRecentForm
    common_opponent_results: list[CommonOpponentResult]
    rating_a: PowerRating
    rating_b: PowerRating
    simulation: SimulationResult
    verdict: Verdict


def build_matchup_report(
    h2h_games: list[Game],
    recent_games: list[Game],
    team_a: str,
    team_b: str,
    recent_seasons: list[int],
    n_simulations: int,
    home_team: str | None = None,
    neutral_site: bool = False,
    sp_rating_a: float | None = None,
    sp_rating_b: float | None = None,
    notes_a: list[str] | None = None,
    notes_b: list[str] | None = None,
) -> MatchupReport:
    """The whole analysis, given games data -- this is the seam between
    "where did the data come from" (cfbd_client.py, or tests with a
    hand-built games list) and everything else, which has no idea.
    """
    recent_seasons_desc = sorted(recent_seasons, reverse=True)

    summary = build_head_to_head(h2h_games, team_a, team_b)
    form_a = build_recent_form(recent_games, team_a, recent_seasons)
    form_b = build_recent_form(recent_games, team_b, recent_seasons)
    shared = common_opponents(recent_games, team_a, team_b, recent_seasons)

    rating_a = build_power_rating(
        recent_games, team_a, recent_seasons_desc, form_a.strength_of_schedule, sp_rating_a
    )
    rating_b = build_power_rating(
        recent_games, team_b, recent_seasons_desc, form_b.strength_of_schedule, sp_rating_b
    )

    std_a = scoring_std_dev(recent_games, team_a, recent_seasons)
    std_b = scoring_std_dev(recent_games, team_b, recent_seasons)

    simulation = simulate_game(
        team_a,
        team_b,
        rating_a.expected_points,
        rating_b.expected_points,
        std_a,
        std_b,
        n_simulations=n_simulations,
        home_team=home_team,
        neutral_site=neutral_site,
    )

    continuity_a = build_continuity(team_a, notes=notes_a)
    continuity_b = build_continuity(team_b, notes=notes_b)
    verdict = build_verdict(simulation, summary, form_a, form_b, continuity_a, continuity_b)

    return MatchupReport(
        h2h=summary,
        form_a=form_a,
        form_b=form_b,
        common_opponent_results=shared,
        rating_a=rating_a,
        rating_b=rating_b,
        simulation=simulation,
        verdict=verdict,
    )
