from .models import Game, PowerRating

# --- Every number below is a knob. Change it, re-run, see what shifts. ---

# Most recent season first. A season further back than this list gets the
# last weight in it repeated -- "recent form matters more than old history"
# is the explicit design goal, this is where that's actually implemented.
SEASON_RECENCY_WEIGHTS = [0.5, 0.3, 0.2]

# How much of a team's strength-of-schedule (its opponents' own average
# margin) gets folded into its rating. Higher = rewards a hard schedule more.
SOS_WEIGHT = 0.25

# When an external rating (e.g. SP+) is supplied, how much it counts vs. our
# own recency-weighted margin calc. 0.0 ignores it entirely, 1.0 uses only it.
EXTERNAL_RATING_WEIGHT = 0.4

# A rough FBS-average points-per-game anchor, used only to turn a margin-based
# "rating" into a plausible raw score for the simulator to work with.
BASELINE_EXPECTED_POINTS = 27.0

# A rough FBS-average of offensive plays run per team per game -- the anchor
# the tempo adjustment below measures a team's own pace against. Same spirit
# as BASELINE_EXPECTED_POINTS: an approximation, not a value computed from
# the full FBS field each run, documented as such rather than presented as
# more precise than it is.
#
# This exists because a real backtest caught the model misreading a
# low-possession team as weak: Navy (a triple-option team that runs fewer,
# longer-clock-eating plays than almost anyone in FBS) was favored 61% over
# UAB and lost, and a separate Army vs. Temple game projected a total of 60
# when the real combined score was 38. `points_for_per_game` /
# `points_against_per_game` -- everything this model was built from -- bakes
# in how many possessions a team's games tend to have, with no way to tell
# "fewer points because weaker" apart from "fewer points because fewer
# chances to score."
LEAGUE_AVERAGE_PLAYS_PER_GAME = 70.0


def plays_per_game(total_plays: int | None, games_played: int) -> float | None:
    """`total_plays` is a whole season's worth (from CFBD's advanced season
    stats -- see cfbd_client.fetch_team_plays); dividing by the number of
    games that team actually played (already known from the games data
    already fetched for everything else) turns it into the per-game pace
    figure the rest of this module compares against league average. None
    when there's nothing to divide -- a team with no games yet, or no plays
    data available for this team/year -- rather than a division error or a
    misleading 0.0 that would read as "runs no plays at all."
    """
    if not total_plays or not games_played:
        return None
    return total_plays / games_played


def pace_factor(team_plays_per_game: float | None) -> float:
    """How a team's own tempo compares to a league-average team: 1.0 is
    exactly average, below 1.0 means fewer possessions per game than
    average (Navy, Army, Air Force and anyone else running a slow,
    clock-eating offense), above 1.0 means more.

    None -- no pace data for this team -- is treated as exactly average
    (1.0) rather than skipping the adjustment: a report with pace data for
    one team and none for the other must not silently adjust one team's
    rating and leave the other's untouched for a reason that has nothing to
    do with which team is actually better.
    """
    if team_plays_per_game is None or team_plays_per_game <= 0:
        return 1.0
    return team_plays_per_game / LEAGUE_AVERAGE_PLAYS_PER_GAME


def game_pace_factor(team_a_plays_per_game: float | None, team_b_plays_per_game: float | None) -> float:
    """The actual expected pace of *this* matchup -- both teams' own tempo,
    averaged, relative to league average.

    This is a second, separate adjustment from `pace_factor` above, and
    deliberately not the same number: `pace_factor` strips pace out of a
    team's own rating so a slow-tempo team's real quality isn't
    undervalued (what fixes the Navy mis-call). This one puts pace back in
    at the point where two specific teams' *expected points* are combined
    into a simulated game -- two slow-tempo teams playing each other really
    will produce a slower, lower-scoring game than either would against a
    league-average opponent, which is the Army/Temple total miss. Applying
    only the first and not this one would correctly rate Navy as better
    than their raw points suggested, while still projecting a normal-pace
    total for a game that will not play out at a normal pace.
    """
    return (pace_factor(team_a_plays_per_game) + pace_factor(team_b_plays_per_game)) / 2


def season_margins(games: list[Game], team: str, seasons: list[int]) -> dict[int, float]:
    """Average scoring margin per season, for whichever seasons the team actually played."""
    margins: dict[int, float] = {}
    for season in seasons:
        season_games = [
            g for g in games if g.season == season and (g.home_team == team or g.away_team == team)
        ]
        if season_games:
            values = [g.margin_for(team) for g in season_games]
            margins[season] = sum(values) / len(values)
    return margins


def weighted_recent_margin(games: list[Game], team: str, seasons_desc: list[int]) -> float | None:
    """seasons_desc must be ordered most-recent-season-first."""
    margins = season_margins(games, team, seasons_desc)
    weighted_sum, weight_used = 0.0, 0.0

    for i, season in enumerate(seasons_desc):
        if season not in margins:
            continue
        weight = SEASON_RECENCY_WEIGHTS[i] if i < len(SEASON_RECENCY_WEIGHTS) else SEASON_RECENCY_WEIGHTS[-1]
        weighted_sum += margins[season] * weight
        weight_used += weight

    return (weighted_sum / weight_used) if weight_used > 0 else None


def build_power_rating(
    games: list[Game],
    team: str,
    seasons_desc: list[int],
    strength_of_schedule: float | None,
    external_rating: float | None = None,
    team_plays_per_game: float | None = None,
) -> PowerRating:
    margin = weighted_recent_margin(games, team, seasons_desc)
    margin_component = margin if margin is not None else 0.0

    # Re-expresses the margin at league-average pace: dividing by a pace
    # factor below 1.0 (fewer possessions than average) scales a
    # low-tempo team's margin *up*, because the same margin achieved with
    # fewer opportunities implies better-than-it-looks per-possession
    # play. A simplification (margin isn't perfectly linear in play
    # count), but a documented, explainable one -- see
    # LEAGUE_AVERAGE_PLAYS_PER_GAME's comment for why this exists at all.
    pace = pace_factor(team_plays_per_game)
    if pace != 1.0:
        margin_component = margin_component / pace

    sos_component = (strength_of_schedule or 0.0) * SOS_WEIGHT

    rating = margin_component + sos_component
    components = {
        "recency_weighted_margin": margin_component,
        "strength_of_schedule_adjustment": sos_component,
    }
    if team_plays_per_game is not None:
        components["pace_factor"] = pace

    if external_rating is not None:
        components["external_rating"] = external_rating
        components["own_calc_before_blend"] = rating
        rating = (rating * (1 - EXTERNAL_RATING_WEIGHT)) + (external_rating * EXTERNAL_RATING_WEIGHT)

    return PowerRating(
        team=team,
        rating=rating,
        expected_points=BASELINE_EXPECTED_POINTS + (rating / 2),
        components=components,
    )
