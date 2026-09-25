import pandas as pd

from .teams import normalize_team


def current_nfl_week(games_df: pd.DataFrame, season: int) -> int:
    """The earliest week this season with a game not yet played.

    Falls back to the last week of the season if everything's been played
    (the season is over) rather than raising — an edge case, not an error.
    """
    season_games = games_df[games_df["season"] == season]
    unplayed = season_games[season_games["home_score"].isna()]
    if unplayed.empty:
        return int(season_games["week"].max())
    return int(unplayed["week"].min())


def team_opponent_for_week(team: str, season: int, week: int, games_df: pd.DataFrame) -> str | None:
    """The opponent a team plays in a given week, or None on a bye."""
    team_norm = normalize_team(team)
    week_games = games_df[(games_df["season"] == season) & (games_df["week"] == week)]
    matches = week_games[
        (week_games["home_team"].apply(normalize_team) == team_norm)
        | (week_games["away_team"].apply(normalize_team) == team_norm)
    ]
    if matches.empty:
        return None

    row = matches.iloc[0]
    home = normalize_team(row["home_team"])
    away = normalize_team(row["away_team"])
    return away if home == team_norm else home
