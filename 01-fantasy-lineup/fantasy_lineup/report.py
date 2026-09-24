import pandas as pd

from .continuity import build_continuity
from .models import PlayerReport, PlayerWeek, TeamMatchupTendency
from .nfl_data import espn_id_to_gsis
from .player_history import build_player_history, empty_player_history
from .team_tendencies import build_team_tendency

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def build_player_reports(
    players: list[PlayerWeek],
    weekly_df: pd.DataFrame,
    games_df: pd.DataFrame,
    crosswalk: pd.DataFrame,
    current_season: int,
    scoring: str,
    team_seasons: list[int],
) -> list[PlayerReport]:
    """Build a full matchup report for every skill-position roster player.

    K and DST are skipped — a matchup history in the same shape doesn't mean
    much for them, so they're left out of the report entirely rather than
    shown with empty numbers.
    """
    tendency_cache: dict[tuple[str, str], TeamMatchupTendency] = {}
    reports = []

    for player in players:
        if player.position not in SKILL_POSITIONS:
            continue

        gsis_id = espn_id_to_gsis(player.espn_id, crosswalk) if player.espn_id else None
        if gsis_id is None:
            history = empty_player_history(player.name, player.position, player.pro_opponent)
        else:
            history = build_player_history(
                weekly_df, gsis_id, player.name, player.position, player.pro_opponent, scoring
            )

        cache_key = (player.pro_team, player.pro_opponent)
        if cache_key not in tendency_cache:
            tendency_cache[cache_key] = build_team_tendency(
                weekly_df, games_df, player.pro_team, player.pro_opponent, team_seasons
            )
        tendency = tendency_cache[cache_key]

        continuity = build_continuity(
            games_df, player.pro_team, player.pro_opponent, current_season, team_seasons
        )

        reports.append(PlayerReport(player=player, history=history, team_tendency=tendency, continuity=continuity))

    return reports
