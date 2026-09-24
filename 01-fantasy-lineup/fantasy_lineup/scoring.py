from typing import Mapping

# Standard fantasy scoring weights. Close to ESPN's own defaults, not an
# exact match for every league's custom rules (bonus thresholds etc.) —
# good enough for comparing a player's history against themself.
_PASS_YARD_PT = 1 / 25
_PASS_TD_PT = 4
_INTERCEPTION_PT = -2
_RUSH_YARD_PT = 1 / 10
_RUSH_TD_PT = 6
_REC_YARD_PT = 1 / 10
_REC_TD_PT = 6
_FUMBLE_LOST_PT = -2

RECEPTION_BONUS = {
    "standard": 0.0,
    "half_ppr": 0.5,
    "ppr": 1.0,
}


def fantasy_points(stats: Mapping[str, float], scoring: str = "ppr") -> float:
    reception_pt = RECEPTION_BONUS.get(scoring, RECEPTION_BONUS["ppr"])

    def get(key: str) -> float:
        value = stats.get(key, 0) or 0
        return float(value)

    return (
        get("passing_yards") * _PASS_YARD_PT
        + get("passing_tds") * _PASS_TD_PT
        + get("interceptions") * _INTERCEPTION_PT
        + get("rushing_yards") * _RUSH_YARD_PT
        + get("rushing_tds") * _RUSH_TD_PT
        + get("receiving_yards") * _REC_YARD_PT
        + get("receiving_tds") * _REC_TD_PT
        + get("receptions") * reception_pt
        + get("fumbles_lost") * _FUMBLE_LOST_PT
    )
