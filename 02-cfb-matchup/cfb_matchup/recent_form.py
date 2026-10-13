import statistics

from .models import CommonOpponentResult, Game, TeamRecentForm
from .simulate import HOME_FIELD_ADVANTAGE

# How many home and away games are needed before trusting a team's *own*
# home-field split over the flat league-average constant. A 3-season
# window is maybe 6-9 home games and 6-9 away games for a typical team --
# fewer than this at either venue is as likely to reflect a scheduling
# quirk (every ranked opponent on the road, every patsy at home) as real
# home-field value, so team_home_field_edge falls back to the same flat
# number every team used before it existed.
MIN_GAMES_PER_VENUE_FOR_HOME_EDGE = 3


def team_games(games: list[Game], team: str, seasons: list[int]) -> list[Game]:
    return [g for g in games if g.season in seasons and (g.home_team == team or g.away_team == team)]


def scoring_std_dev(games: list[Game], team: str, seasons: list[int], default: float = 10.0) -> float:
    """How much a team's own point total actually varies game to game --
    feeds the simulator's spread of outcomes. Falls back to a league-ish
    default when there's too little history to compute a real one from."""
    relevant = team_games(games, team, seasons)
    points_for = [g.home_score if g.home_team == team else g.away_score for g in relevant]
    if len(points_for) < 2:
        return default
    return statistics.stdev(points_for)


def team_home_field_edge(
    games: list[Game],
    team: str,
    seasons: list[int],
    min_games_each_venue: int = MIN_GAMES_PER_VENUE_FOR_HOME_EDGE,
    league_average: float = HOME_FIELD_ADVANTAGE,
) -> float:
    """How many points hosting is actually worth for this specific team --
    half the gap between its own average home margin and its own average
    away margin over `seasons`. Half, not the full gap, because that's the
    standard way a single league-wide number like `HOME_FIELD_ADVANTAGE`
    is itself derived (attributing half the home/away swing to a boost for
    the host, half to a penalty for the visitor) -- this computes the same
    quantity per team instead of across the whole league, so it's a
    like-for-like replacement rather than a differently-scaled new number.

    Falls back to `league_average` -- the flat number every team used
    before this existed -- when there isn't `min_games_each_venue` games
    at *both* venues to trust (see the module constant above), and the
    result is clamped to [0, 2x league_average]: a small sample implying
    a 15-point home edge is noise, not a program with a legitimately
    enormous home-field advantage, and letting it through unclamped would
    let exactly the kind of fluke this fallback exists to catch back in
    through the other side.
    """
    relevant = team_games(games, team, seasons)
    home_margins = [g.margin_for(team) for g in relevant if g.venue_for(team) == "home"]
    away_margins = [g.margin_for(team) for g in relevant if g.venue_for(team) == "away"]

    if len(home_margins) < min_games_each_venue or len(away_margins) < min_games_each_venue:
        return league_average

    home_avg = sum(home_margins) / len(home_margins)
    away_avg = sum(away_margins) / len(away_margins)
    edge = (home_avg - away_avg) / 2
    return max(0.0, min(edge, league_average * 2))


def build_recent_form(games: list[Game], team: str, seasons: list[int]) -> TeamRecentForm:
    relevant = team_games(games, team, seasons)

    wins = sum(1 for g in relevant if g.winner == team)
    losses = sum(1 for g in relevant if g.winner is not None and g.winner != team)

    points_for = [g.home_score if g.home_team == team else g.away_score for g in relevant]
    points_against = [g.away_score if g.home_team == team else g.home_score for g in relevant]

    home_games = [g for g in relevant if g.venue_for(team) == "home"]
    away_games = [g for g in relevant if g.venue_for(team) == "away"]

    return TeamRecentForm(
        team=team,
        seasons=seasons,
        games_played=len(relevant),
        wins=wins,
        losses=losses,
        points_for_per_game=(sum(points_for) / len(points_for)) if points_for else None,
        points_against_per_game=(sum(points_against) / len(points_against)) if points_against else None,
        home_record=_record(home_games, team),
        away_record=_record(away_games, team),
        strength_of_schedule=_strength_of_schedule(games, relevant, team, seasons),
    )


def common_opponents(
    games: list[Game], team_a: str, team_b: str, seasons: list[int]
) -> list[CommonOpponentResult]:
    """Shared opponents in the window, each team's most recent result against them."""
    a_latest = _latest_result_per_opponent(team_games(games, team_a, seasons), team_a)
    b_latest = _latest_result_per_opponent(team_games(games, team_b, seasons), team_b)

    results = []
    for opponent in sorted(set(a_latest) & set(b_latest)):
        ga, gb = a_latest[opponent], b_latest[opponent]
        results.append(
            CommonOpponentResult(
                opponent=opponent,
                team_a_won=ga.winner == team_a,
                team_a_score=_own_score(ga, team_a),
                team_a_opp_score=_opp_score(ga, team_a),
                team_b_won=gb.winner == team_b,
                team_b_score=_own_score(gb, team_b),
                team_b_opp_score=_opp_score(gb, team_b),
            )
        )
    return results


def _record(games: list[Game], team: str) -> tuple[int, int]:
    wins = sum(1 for g in games if g.winner == team)
    losses = sum(1 for g in games if g.winner is not None and g.winner != team)
    return wins, losses


def _strength_of_schedule(
    all_games: list[Game], team_schedule: list[Game], team: str, seasons: list[int]
) -> float | None:
    opponents = {g.opponent_of(team) for g in team_schedule}
    diffs = []
    for opponent in opponents:
        opp_games = team_games(all_games, opponent, seasons)
        if opp_games:
            margins = [g.margin_for(opponent) for g in opp_games]
            diffs.append(sum(margins) / len(margins))
    return (sum(diffs) / len(diffs)) if diffs else None


def _latest_result_per_opponent(schedule: list[Game], team: str) -> dict[str, Game]:
    latest: dict[str, Game] = {}
    for g in sorted(schedule, key=lambda g: (g.season, g.week)):
        latest[g.opponent_of(team)] = g  # later meetings overwrite earlier ones
    return latest


def _own_score(g: Game, team: str) -> int:
    return g.home_score if g.home_team == team else g.away_score


def _opp_score(g: Game, team: str) -> int:
    return g.away_score if g.home_team == team else g.home_score
