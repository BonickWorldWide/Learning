import json
from pathlib import Path

from .models import Game


def load_bundle_file(path: Path) -> dict:
    """A JSON file matching Gridiron Fetch's output shape -- games data
    pulled by the artifact (client-side, in the browser, past any network
    block this environment has) instead of cfbd_client.py fetching it here.
    """
    if not path.exists():
        raise FileNotFoundError(f"No data file at {path}.")
    return json.loads(path.read_text())


def games_from_bundle(raw_games: list[dict]) -> list[Game]:
    return [
        Game(
            season=g["season"],
            week=g.get("week", 0),
            date=g.get("date", ""),
            home_team=g["home_team"],
            away_team=g["away_team"],
            home_score=g["home_score"],
            away_score=g["away_score"],
            neutral_site=bool(g.get("neutral_site", False)),
        )
        for g in raw_games
    ]
