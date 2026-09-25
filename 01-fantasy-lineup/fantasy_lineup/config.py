import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"

# "Career" really means "as far back as we can cheaply look" — a player's
# actual rookie season isn't available without another lookup, so this is a
# practical stand-in that covers essentially every fantasy-relevant player.
DEFAULT_PLAYER_SEASONS_LOOKBACK = 10
DEFAULT_TEAM_SEASONS_LOOKBACK = 5
DEFAULT_SCORING = "ppr"


@dataclass
class Config:
    league_id: int | None
    team_id: int | None
    year: int
    espn_s2: str | None
    swid: str | None
    scoring: str
    player_seasons_lookback: int
    team_seasons_lookback: int


def load_config(config_file: Path = DEFAULT_CONFIG_FILE) -> Config:
    """league_id/team_id are only required for the ESPN client path — the
    manual-roster path doesn't touch ESPN at all, so a config file with
    neither (or no config file at all) is valid; get_week_players() is what
    enforces they're present when ESPN mode actually needs them.
    """
    data = {}
    if config_file.exists():
        data = json.loads(config_file.read_text())

    league_id = data.get("league_id")
    team_id = data.get("team_id")

    return Config(
        league_id=int(league_id) if league_id is not None else None,
        team_id=int(team_id) if team_id is not None else None,
        year=int(data.get("year", 2026)),
        espn_s2=data.get("espn_s2") or os.environ.get("ESPN_S2") or None,
        swid=data.get("swid") or os.environ.get("ESPN_SWID") or None,
        scoring=data.get("scoring", DEFAULT_SCORING),
        player_seasons_lookback=int(data.get("player_seasons_lookback", DEFAULT_PLAYER_SEASONS_LOOKBACK)),
        team_seasons_lookback=int(data.get("team_seasons_lookback", DEFAULT_TEAM_SEASONS_LOOKBACK)),
    )
