import pytest

from cfb_matchup.cli import _resolve_vegas_spread


def test_resolve_vegas_spread_from_favorite_side():
    # Team_a favored by 7.5, shown as a sportsbook would show it (-7.5).
    assert _resolve_vegas_spread(line_a=-7.5, line_b=None) == 7.5


def test_resolve_vegas_spread_from_underdog_side():
    assert _resolve_vegas_spread(line_a=3.5, line_b=None) == -3.5


def test_resolve_vegas_spread_from_team_b_line_alone():
    # Team_b getting +7.5 means team_a is favored by 7.5.
    assert _resolve_vegas_spread(line_a=None, line_b=7.5) == 7.5


def test_resolve_vegas_spread_accepts_both_sides_when_consistent():
    assert _resolve_vegas_spread(line_a=-7.5, line_b=7.5) == 7.5


def test_resolve_vegas_spread_rejects_inconsistent_sides():
    with pytest.raises(ValueError, match="don't look like the same line"):
        _resolve_vegas_spread(line_a=-7.5, line_b=3.0)


def test_resolve_vegas_spread_none_when_neither_given():
    assert _resolve_vegas_spread(line_a=None, line_b=None) is None
