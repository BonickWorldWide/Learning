import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_H2H_SEASONS_BACK = 50
DEFAULT_RECENT_SEASONS = 3
DEFAULT_N_SIMULATIONS = 10_000


@dataclass
class Config:
    api_key: str | None
    h2h_seasons_back: int
    recent_seasons: int
    n_simulations: int
    use_sp_plus: bool


def load_config(config_file: Path = DEFAULT_CONFIG_FILE) -> Config:
    data = {}
    if config_file.exists():
        data = json.loads(config_file.read_text())

    return Config(
        api_key=data.get("api_key") or os.environ.get("CFBD_API_KEY") or None,
        h2h_seasons_back=int(data.get("h2h_seasons_back", DEFAULT_H2H_SEASONS_BACK)),
        recent_seasons=int(data.get("recent_seasons", DEFAULT_RECENT_SEASONS)),
        n_simulations=int(data.get("n_simulations", DEFAULT_N_SIMULATIONS)),
        use_sp_plus=bool(data.get("use_sp_plus", True)),
    )
