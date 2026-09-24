import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class Config:
    league_id: int
    team_id: int
    year: int
    espn_s2: str | None
    swid: str | None


def load_config(config_file: Path = DEFAULT_CONFIG_FILE) -> Config:
    if not config_file.exists():
        raise FileNotFoundError(
            f"No config file at {config_file}.\n"
            "Copy config.example.json to config.json and fill in your league_id and team_id."
        )

    data = json.loads(config_file.read_text())
    return Config(
        league_id=int(data["league_id"]),
        team_id=int(data["team_id"]),
        year=int(data.get("year", 2026)),
        espn_s2=data.get("espn_s2") or os.environ.get("ESPN_S2") or None,
        swid=data.get("swid") or os.environ.get("ESPN_SWID") or None,
    )
