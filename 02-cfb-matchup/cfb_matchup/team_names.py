import difflib


def resolve_team_name(
    input_name: str, known_teams: list[str], alternate_names: dict[str, list[str]] | None = None
) -> str | None:
    """Matches whatever a person typed against CollegeFootballData's exact
    school names, case- and whitespace-insensitively, then against each
    school's known alternate names (nicknames, abbreviations CFBD itself
    lists). None if nothing matches.

    Every other module compares `Game.home_team`/`away_team` to `team_a`/
    `team_b` with plain string equality (see h2h.py, recent_form.py) --
    that only ever works if team_a/team_b already carry CFBD's exact
    spelling. Resolving once here, before anything else touches the name,
    is what makes "Virginia tech" (lowercase t) work instead of silently
    returning zero games for every section of the report.
    """
    normalized_input = input_name.strip().casefold()

    for school in known_teams:
        if school.casefold() == normalized_input:
            return school

    if alternate_names:
        for school, alts in alternate_names.items():
            if normalized_input in {a.strip().casefold() for a in alts if a}:
                return school

    return None


def suggest_team_names(input_name: str, known_teams: list[str], limit: int = 3) -> list[str]:
    return difflib.get_close_matches(input_name, known_teams, n=limit, cutoff=0.5)
