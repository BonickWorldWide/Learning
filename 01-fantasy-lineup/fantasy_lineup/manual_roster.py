import json
from pathlib import Path

import pandas as pd

from .models import PlayerWeek
from .rosters import latest_team_for_player
from .schedule import team_opponent_for_week

DEFAULT_ROSTER_FILE = Path(__file__).resolve().parent.parent / "roster.json"


def load_roster_entries(roster_file: Path = DEFAULT_ROSTER_FILE) -> list[dict]:
    if not roster_file.exists():
        raise FileNotFoundError(
            f"No roster file at {roster_file}.\n"
            "Copy roster.example.json to roster.json and fill in your players."
        )
    return json.loads(roster_file.read_text())


def resolve_roster(
    entries: list[dict],
    current_rosters: pd.DataFrame,
    games_df: pd.DataFrame,
    season: int,
    week: int,
) -> list[PlayerWeek]:
    """Turn {"name", "position", "slot"} entries into PlayerWeeks.

    Team and opponent are looked up, not typed in — a player's current NFL
    team can change mid-season (trades), and the opponent is whatever the
    real schedule says for that team in this week. A player not found in
    the roster data (name typo, or truly obscure) still gets a PlayerWeek,
    just with no team/opponent, so one bad entry doesn't sink the report.
    """
    players = []
    for entry in entries:
        name = entry["name"]
        position = entry["position"]
        slot = entry.get("slot", "BE")

        row = latest_team_for_player(name, current_rosters)
        team = row["team"] if row is not None else ""
        gsis_id = row["gsis_id"] if row is not None and pd.notna(row["gsis_id"]) else None
        opponent = team_opponent_for_week(team, season, week, games_df) if team else None

        players.append(
            PlayerWeek(
                name=name,
                position=position,
                lineup_slot=slot,
                pro_team=team,
                pro_opponent=opponent or "BYE",
                gsis_id=gsis_id,
            )
        )
    return players
