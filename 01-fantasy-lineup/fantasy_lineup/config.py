import json
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
    year: int
    scoring: str
    player_seasons_lookback: int
    team_seasons_lookback: int


def load_config(config_file: Path = DEFAULT_CONFIG_FILE) -> Config:
    """A config file is entirely optional — every field has a default, so
    a first run with no config.json at all still works."""
    data = {}
    if config_file.exists():
        data = json.loads(config_file.read_text())

    return Config(
        year=int(data.get("year", 2026)),
        scoring=data.get("scoring", DEFAULT_SCORING),
        player_seasons_lookback=int(data.get("player_seasons_lookback", DEFAULT_PLAYER_SEASONS_LOOKBACK)),
        team_seasons_lookback=int(data.get("team_seasons_lookback", DEFAULT_TEAM_SEASONS_LOOKBACK)),
    )
