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
) -> PowerRating:
    margin = weighted_recent_margin(games, team, seasons_desc)
    margin_component = margin if margin is not None else 0.0
    sos_component = (strength_of_schedule or 0.0) * SOS_WEIGHT

    rating = margin_component + sos_component
    components = {
        "recency_weighted_margin": margin_component,
        "strength_of_schedule_adjustment": sos_component,
    }

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
