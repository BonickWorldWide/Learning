# ESPN and nflverse mostly agree on team abbreviations, but a handful of
# relocated/rebranded franchises are spelled differently between the two —
# joining on the raw strings would silently drop those teams' history.
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
