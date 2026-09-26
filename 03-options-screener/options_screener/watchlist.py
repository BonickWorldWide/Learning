import json
from pathlib import Path

DEFAULT_WATCHLIST_FILE = Path(__file__).resolve().parent.parent / "watchlist.json"


def load_watchlist(path: Path = DEFAULT_WATCHLIST_FILE) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(
            f"No watchlist file at {path}. Copy watchlist.example.json to watchlist.json and edit it."
        )
    tickers = json.loads(path.read_text())
    if not isinstance(tickers, list) or not all(isinstance(t, str) for t in tickers):
        raise ValueError(f"{path} must be a JSON array of ticker strings.")
    return [t.strip().upper() for t in tickers]
