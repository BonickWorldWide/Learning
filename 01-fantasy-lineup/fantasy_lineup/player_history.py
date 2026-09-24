import pandas as pd

from .models import PlayerMatchupHistory
from .scoring import fantasy_points
from .teams import normalize_team

STAT_KEYS_BY_POSITION = {
    "QB": ["attempts", "passing_yards", "passing_tds", "interceptions", "rushing_yards"],
    "RB": ["carries", "rushing_yards", "rushing_tds", "targets", "receptions", "receiving_yards"],
    "WR": ["targets", "receptions", "receiving_yards", "receiving_tds"],
    "TE": ["targets", "receptions", "receiving_yards", "receiving_tds"],
}


def empty_player_history(player_name: str, position: str, opponent: str) -> PlayerMatchupHistory:
    """Used when a roster player can't be identified in the historical data at all."""
    return PlayerMatchupHistory(
        player_name=player_name,
        position=position,
        opponent=opponent,
        games_vs_opponent=0,
        career_games=0,
        ppg_vs_opponent=None,
        career_ppg=None,
        ppg_delta=None,
    )


def build_player_history(
    weekly_df: pd.DataFrame,
    player_id: str,
    player_name: str,
    position: str,
    opponent: str,
    scoring: str = "ppr",
) -> PlayerMatchupHistory:
    opponent_norm = normalize_team(opponent)
    player_rows = weekly_df[weekly_df["player_id"] == player_id]
    vs_rows = player_rows[player_rows["opponent_team"].apply(normalize_team) == opponent_norm]

    career_games = len(player_rows)
    games_vs_opponent = len(vs_rows)

    career_ppg = _mean_points(player_rows, scoring) if career_games else None
    ppg_vs_opponent = _mean_points(vs_rows, scoring) if games_vs_opponent else None
    ppg_delta = (
        ppg_vs_opponent - career_ppg
        if career_ppg is not None and ppg_vs_opponent is not None
        else None
    )

    stat_keys = STAT_KEYS_BY_POSITION.get(position, [])
    stat_averages_career = _stat_averages(player_rows, stat_keys) if career_games else {}
    stat_averages_vs_opponent = _stat_averages(vs_rows, stat_keys) if games_vs_opponent else {}

    return PlayerMatchupHistory(
        player_name=player_name,
        position=position,
        opponent=opponent_norm,
        games_vs_opponent=games_vs_opponent,
        career_games=career_games,
        ppg_vs_opponent=ppg_vs_opponent,
        career_ppg=career_ppg,
        ppg_delta=ppg_delta,
        stat_averages_vs_opponent=stat_averages_vs_opponent,
        stat_averages_career=stat_averages_career,
    )


def _mean_points(rows: pd.DataFrame, scoring: str) -> float:
    return float(rows.apply(lambda row: fantasy_points(row, scoring), axis=1).mean())


def _stat_averages(rows: pd.DataFrame, stat_keys: list[str]) -> dict[str, float]:
    return {key: float(rows[key].mean()) for key in stat_keys if key in rows.columns}
