import pandas as pd

from .models import TeamMatchupTendency
from .teams import normalize_team

POSITION_GROUPS = ["QB", "RB", "WR", "TE"]


def build_team_tendency(
    weekly_df: pd.DataFrame,
    games_df: pd.DataFrame,
    team: str,
    opponent: str,
    seasons: list[int],
) -> TeamMatchupTendency:
    team_norm = normalize_team(team)
    opponent_norm = normalize_team(opponent)

    rows = weekly_df[
        (weekly_df["recent_team"].apply(normalize_team) == team_norm)
        & (weekly_df["opponent_team"].apply(normalize_team) == opponent_norm)
        & (weekly_df["season"].isin(seasons))
    ]

    if rows.empty:
        return TeamMatchupTendency(
            team=team_norm,
            opponent=opponent_norm,
            games=0,
            seasons_considered=seasons,
            run_rate=None,
            pass_rate=None,
            avg_rush_yards=None,
            avg_pass_yards=None,
            avg_points_for=None,
        )

    per_game = (
        rows.groupby(["season", "week"])
        .agg(
            rush_att=("carries", "sum"),
            pass_att=("attempts", "sum"),
            rush_yards=("rushing_yards", "sum"),
            pass_yards=("passing_yards", "sum"),
        )
        .reset_index()
    )
    per_game["total_plays"] = per_game["rush_att"] + per_game["pass_att"]
    valid_plays = per_game[per_game["total_plays"] > 0]

    if not valid_plays.empty:
        run_rate = float((valid_plays["rush_att"] / valid_plays["total_plays"]).mean())
        pass_rate = 1 - run_rate
    else:
        run_rate = None
        pass_rate = None

    position_volume_share, top_volume_player = _position_volume(rows)

    return TeamMatchupTendency(
        team=team_norm,
        opponent=opponent_norm,
        games=len(per_game),
        seasons_considered=seasons,
        run_rate=run_rate,
        pass_rate=pass_rate,
        avg_rush_yards=float(per_game["rush_yards"].mean()),
        avg_pass_yards=float(per_game["pass_yards"].mean()),
        avg_points_for=_avg_points_for(games_df, team_norm, opponent_norm, seasons),
        position_volume_share=position_volume_share,
        top_volume_player=top_volume_player,
    )


def _position_volume(rows: pd.DataFrame) -> tuple[dict[str, float], dict[str, str]]:
    volume = rows.copy()
    volume["volume"] = volume[["targets", "carries"]].fillna(0).sum(axis=1)
    total_volume = volume["volume"].sum()

    position_volume_share: dict[str, float] = {}
    top_volume_player: dict[str, str] = {}
    for position in POSITION_GROUPS:
        pos_rows = volume[volume["position"] == position]
        if total_volume > 0:
            position_volume_share[position] = float(pos_rows["volume"].sum() / total_volume)
        if not pos_rows.empty:
            by_player = pos_rows.groupby("player_name")["volume"].sum()
            top_volume_player[position] = by_player.idxmax()

    return position_volume_share, top_volume_player


def _avg_points_for(
    games_df: pd.DataFrame, team: str, opponent: str, seasons: list[int]
) -> float | None:
    g = games_df[games_df["season"].isin(seasons)]
    home_scores = g[
        (g["home_team"].apply(normalize_team) == team) & (g["away_team"].apply(normalize_team) == opponent)
    ]["home_score"]
    away_scores = g[
        (g["away_team"].apply(normalize_team) == team) & (g["home_team"].apply(normalize_team) == opponent)
    ]["away_score"]
    scores = pd.concat([home_scores, away_scores]).dropna()
    return float(scores.mean()) if len(scores) else None
