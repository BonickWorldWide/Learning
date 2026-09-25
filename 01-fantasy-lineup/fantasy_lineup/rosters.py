import re

import pandas as pd

# "Michael Pittman Jr." typed in vs "Michael Pittman" in the data (or the
# reverse) is common enough that suffix presence can't be relied on from
# either side — stripped and compared without it as the second attempt.
_SUFFIX_RE = re.compile(r"\s+(jr\.?|sr\.?|i{2,3}|iv)$", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    return _SUFFIX_RE.sub("", name.strip()).lower()


def latest_team_for_player(name: str, rosters: pd.DataFrame) -> pd.Series | None:
    """Most recent roster row for a player, matched by name.

    Tried in order: exact (case-insensitive) match, then a suffix-blind
    match (handles "Jr."/"Sr."/"II" etc. present on one side but not the
    other), then a substring match as a last resort. Each is tried only if
    the one before it found nothing, since a looser match can collide on a
    shared surname.
    """
    exact = rosters[rosters["full_name"].str.lower() == name.lower()]
    if not exact.empty:
        return exact.sort_values("week").iloc[-1]

    normalized_query = _normalize_name(name)
    normalized_match = rosters[rosters["full_name"].apply(_normalize_name) == normalized_query]
    if not normalized_match.empty:
        return normalized_match.sort_values("week").iloc[-1]

    substring = rosters[rosters["full_name"].str.contains(name, case=False, na=False, regex=False)]
    if not substring.empty:
        return substring.sort_values("week").iloc[-1]

    return None
