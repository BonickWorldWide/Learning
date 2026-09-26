import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class Config:
    near_money_band_pct: float
    cheap_max_premium: float
    pop_delta_min: float
    pop_delta_max: float
    pop_max_premium: float
    pop_min_score: float
    risk_free_rate: float

    @property
    def pop_delta_range(self) -> tuple[float, float]:
        return (self.pop_delta_min, self.pop_delta_max)


def load_config(config_file: Path = DEFAULT_CONFIG_FILE) -> Config:
    data = {}
    if config_file.exists():
        data = json.loads(config_file.read_text())

    return Config(
        near_money_band_pct=float(data.get("near_money_band_pct", 0.05)),
        cheap_max_premium=float(data.get("cheap_max_premium", 2.00)),
        pop_delta_min=float(data.get("pop_delta_min", 0.10)),
        pop_delta_max=float(data.get("pop_delta_max", 0.30)),
        pop_max_premium=float(data.get("pop_max_premium", 1.00)),
        pop_min_score=float(data.get("pop_min_score", 0.6)),
        risk_free_rate=float(data.get("risk_free_rate", 0.045)),
    )
