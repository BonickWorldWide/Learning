from pathlib import Path

import nfl_data_py as nfl
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

# Only the columns the rest of the project actually reads — keeps the cached
# parquet files small and makes it obvious what data this tool depends on.
# There's no single "fumbles_lost" column in the source data — it's split
# into sack/rushing/receiving fumbles lost, summed below into one field.
_FUMBLE_COLUMNS = ["sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost"]

WEEKLY_COLUMNS = [
    "player_id",
    "player_name",
    "position",
    "recent_team",
    "opponent_team",
    "season",
    "week",
    "attempts",
    "passing_yards",
    "passing_tds",
    "interceptions",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    *_FUMBLE_COLUMNS,
]

GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"


def get_weekly_stats(seasons: list[int], refresh: bool = False) -> pd.DataFrame:
    """Player-level weekly stats, one season at a time, cached to disk."""
    CACHE_DIR.mkdir(exist_ok=True)
    frames = []
    for year in seasons:
        cache_file = CACHE_DIR / f"weekly_{year}.parquet"
        if refresh or not cache_file.exists():
            df = nfl.import_weekly_data([year], columns=WEEKLY_COLUMNS)
            df["fumbles_lost"] = df[_FUMBLE_COLUMNS].sum(axis=1)
            df = df.drop(columns=_FUMBLE_COLUMNS)
            df.to_parquet(cache_file)
        else:
            df = pd.read_parquet(cache_file)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def get_games(refresh: bool = False) -> pd.DataFrame:
    """Game-level schedule data: scores, head coach and starting QB per game."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / "games.parquet"
    if refresh or not cache_file.exists():
        df = pd.read_csv(GAMES_URL)
        df.to_parquet(cache_file)
    else:
        df = pd.read_parquet(cache_file)
    return df


def get_id_crosswalk(refresh: bool = False) -> pd.DataFrame:
    """ESPN player id -> nflverse (gsis) player id, so lookups don't rely on name matching."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / "ids.parquet"
    if refresh or not cache_file.exists():
        df = nfl.import_ids()[["espn_id", "gsis_id", "name"]]
        df.to_parquet(cache_file)
    else:
        df = pd.read_parquet(cache_file)
    return df


def espn_id_to_gsis(espn_id: str, crosswalk: pd.DataFrame) -> str | None:
    matches = crosswalk[crosswalk["espn_id"] == float(espn_id)]
    if matches.empty:
        return None
    gsis_id = matches.iloc[0]["gsis_id"]
    return gsis_id if pd.notna(gsis_id) else None
