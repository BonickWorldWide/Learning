import pandas as pd

from .models import ContinuityFlags
from .teams import normalize_team


def build_continuity(
    games_df: pd.DataFrame,
    team: str,
    opponent: str,
    current_season: int,
    historical_seasons: list[int],
) -> ContinuityFlags:
    """Automatic head-coach and starting-QB continuity check.

    Only head coach and starting QB are checked — both are in the free
    schedule data. Offensive coordinator changes matter just as much for
    reading whether old tendencies still apply, but there's no free public
    dataset of OC history, so that one stays a manual judgment call.
    """
    team_norm = normalize_team(team)
    opponent_norm = normalize_team(opponent)

    current_team_rows = games_df[
        (games_df["season"] == current_season)
        & (
            (games_df["home_team"].apply(normalize_team) == team_norm)
            | (games_df["away_team"].apply(normalize_team) == team_norm)
        )
    ]

    current_coach = None
    for _, row in current_team_rows.iterrows():
        coach = _coach(row, team_norm)
        if coach:
            current_coach = coach
            break

    played = current_team_rows[current_team_rows["home_score"].notna()]
    notes: list[str] = []
    current_qb = None
    if not played.empty:
        latest = played.sort_values("week").iloc[-1]
        current_qb = _qb(latest, team_norm)
    else:
        notes.append("no games played yet this season — QB continuity not checked yet")

    historical_rows = games_df[
        games_df["season"].isin(historical_seasons)
        & (
            (
                (games_df["home_team"].apply(normalize_team) == team_norm)
                & (games_df["away_team"].apply(normalize_team) == opponent_norm)
            )
            | (
                (games_df["away_team"].apply(normalize_team) == team_norm)
                & (games_df["home_team"].apply(normalize_team) == opponent_norm)
            )
        )
    ]

    prior_coaches = sorted({c for c in (_coach(row, team_norm) for _, row in historical_rows.iterrows()) if c})
    prior_qbs = sorted({q for q in (_qb(row, team_norm) for _, row in historical_rows.iterrows()) if q})

    return ContinuityFlags(
        team=team_norm,
        current_coach=current_coach,
        prior_coaches=prior_coaches,
        current_qb=current_qb,
        prior_qbs=prior_qbs,
        notes=notes,
    )


def _side(row: pd.Series, team_norm: str) -> str:
    return "home" if normalize_team(row["home_team"]) == team_norm else "away"


def _coach(row: pd.Series, team_norm: str) -> str | None:
    value = row[f"{_side(row, team_norm)}_coach"]
    return value if pd.notna(value) else None


def _qb(row: pd.Series, team_norm: str) -> str | None:
    value = row[f"{_side(row, team_norm)}_qb_name"]
    return value if pd.notna(value) else None
