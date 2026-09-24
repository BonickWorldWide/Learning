from fantasy_lineup.teams import normalize_team


def test_known_alias_maps_to_canonical():
    assert normalize_team("WSH") == "WAS"
    assert normalize_team("JAC") == "JAX"
    assert normalize_team("OAK") == "LV"


def test_unaliased_team_passes_through():
    assert normalize_team("SF") == "SF"


def test_lowercase_and_whitespace_are_normalized():
    assert normalize_team(" sd ") == "LAC"
