import json
from pathlib import Path

from .models import Round

DEFAULT_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "rounds.json"


def load_rounds(data_file: Path = DEFAULT_DATA_FILE) -> list[Round]:
    if not data_file.exists():
        return []
    raw = json.loads(data_file.read_text())
    return [Round.from_dict(entry) for entry in raw]


def save_round(round_: Round, data_file: Path = DEFAULT_DATA_FILE) -> None:
    rounds = load_rounds(data_file)
    rounds.append(round_)
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps([r.to_dict() for r in rounds], indent=2))
