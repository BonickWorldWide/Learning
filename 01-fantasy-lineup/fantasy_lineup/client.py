from espn_api.football import League

from .config import Config
from .models import PlayerWeek


def player_from_box_player(bp) -> PlayerWeek:
    """Convert an espn_api BoxPlayer into our own PlayerWeek.

    Goes through getattr() with defaults rather than direct attribute access:
    this is the one boundary in the project touching a third-party library
    whose exact fields can shift between versions, so a missing field should
    show up as a blank/zero value, not crash the whole recommendation.
    """
    return PlayerWeek(
        espn_id=str(getattr(bp, "playerId", "") or ""),
        name=bp.name,
        position=getattr(bp, "position", "") or "",
        lineup_slot=getattr(bp, "slot_position", "BE") or "BE",
        pro_team=getattr(bp, "proTeam", "") or "",
        pro_opponent=getattr(bp, "pro_opponent", "") or "",
    )


def get_week_players(config: Config, week: int | None = None) -> list[PlayerWeek]:
    league = League(
        league_id=config.league_id,
        year=config.year,
        espn_s2=config.espn_s2,
        swid=config.swid,
    )
    week = week or league.current_week
    matchups = league.box_scores(week)

    for matchup in matchups:
        if getattr(matchup.home_team, "team_id", None) == config.team_id:
            lineup = matchup.home_lineup
            break
        if getattr(matchup.away_team, "team_id", None) == config.team_id:
            lineup = matchup.away_lineup
            break
    else:
        raise ValueError(f"team_id {config.team_id} not found in week {week} matchups")

    return [player_from_box_player(bp) for bp in lineup]
