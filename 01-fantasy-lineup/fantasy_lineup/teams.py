# nflverse's own historical data uses the abbreviation a team had at the
# time — old games still say "OAK" or "SD" — while current rosters use the
# team's current one. A career-length lookback spans both, so joining on
# the raw strings would silently drop the pre-relocation half of a team's
# history.
_ALIASES = {
    "WSH": "WAS",
    "JAC": "JAX",
    "LAR": "LA",
    "STL": "LA",
    "SD": "LAC",
    "OAK": "LV",
}


def normalize_team(abbr: str) -> str:
    abbr = (abbr or "").strip().upper()
    return _ALIASES.get(abbr, abbr)
