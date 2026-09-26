from cfb_matchup.team_names import resolve_team_name, suggest_team_names

KNOWN = ["Virginia Tech", "Boston College", "Ohio State", "Michigan"]


def test_exact_match():
    assert resolve_team_name("Virginia Tech", KNOWN) == "Virginia Tech"


def test_case_insensitive_match():
    assert resolve_team_name("virginia tech", KNOWN) == "Virginia Tech"


def test_mixed_case_match():
    assert resolve_team_name("Virginia tech", KNOWN) == "Virginia Tech"


def test_leading_trailing_whitespace_is_ignored():
    assert resolve_team_name("  Boston College  ", KNOWN) == "Boston College"


def test_no_match_returns_none():
    assert resolve_team_name("Boston University", KNOWN) is None


def test_alternate_name_match():
    alts = {"Virginia Tech": ["VT", "Va Tech"]}
    assert resolve_team_name("va tech", KNOWN, alternate_names=alts) == "Virginia Tech"


def test_alternate_names_with_none_entries_are_skipped():
    alts = {"Virginia Tech": [None, "VT"]}
    assert resolve_team_name("vt", KNOWN, alternate_names=alts) == "Virginia Tech"


def test_suggestions_for_a_near_miss():
    suggestions = suggest_team_names("Virginia Teh", KNOWN)
    assert "Virginia Tech" in suggestions


def test_no_suggestions_for_something_unrelated():
    assert suggest_team_names("Zzzzzzzz", KNOWN) == []
