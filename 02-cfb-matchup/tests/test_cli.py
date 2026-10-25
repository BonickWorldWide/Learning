import pytest

from cfb_matchup.cli import _parse_leg, _resolve_vegas_spread


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


def test_parse_leg_with_label():
    prob, odds, label = _parse_leg("0.75,-230,Georgia Tech")
    assert prob == pytest.approx(0.75)
    assert odds == -230
    assert label == "Georgia Tech"


def test_parse_leg_without_label_gets_a_default():
    prob, odds, label = _parse_leg("0.6,150")
    assert prob == pytest.approx(0.6)
    assert odds == 150
    assert "0.6" in label and "150" in label


def test_parse_leg_rejects_a_probability_outside_zero_to_one():
    # A common mistake: typing "75" (a percentage) instead of "0.75".
    with pytest.raises(ValueError, match="between 0 and 1"):
        _parse_leg("75,-230")


def test_parse_leg_rejects_malformed_input():
    with pytest.raises(ValueError, match='PROB,ODDS'):
        _parse_leg("just one field")
    with pytest.raises(ValueError, match="must be a decimal"):
        _parse_leg("not-a-number,-230")
