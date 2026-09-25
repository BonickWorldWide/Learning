import pandas as pd

from fantasy_lineup.rosters import latest_team_for_player


def _rosters():
    return pd.DataFrame(
        [
            {"full_name": "David Montgomery", "team": "DET", "week": 1},
            {"full_name": "David Montgomery", "team": "HOU", "week": 3},  # traded mid-season
            {"full_name": "Chris Godwin", "team": "TB", "week": 2},
        ]
    )


def test_returns_most_recent_week_not_first_match():
    row = latest_team_for_player("David Montgomery", _rosters())
    assert row["team"] == "HOU"
    assert row["week"] == 3


def test_exact_match_preferred_over_substring():
    rosters = pd.DataFrame(
        [
            {"full_name": "Chris Godwin", "team": "TB", "week": 1},
            {"full_name": "Chris Godwin Jr.", "team": "TB", "week": 1},
        ]
    )
    row = latest_team_for_player("Chris Godwin", rosters)
    assert row["full_name"] == "Chris Godwin"


def test_case_insensitive_match():
    row = latest_team_for_player("david montgomery", _rosters())
    assert row["team"] == "HOU"


def test_unknown_player_returns_none():
    assert latest_team_for_player("Nobody Real", _rosters()) is None


def test_query_has_suffix_data_does_not():
    # The real bug: "Michael Pittman Jr." typed in, but the roster data has
    # just "Michael Pittman" -- a plain substring check fails in this
    # direction because the query is longer than the data's name.
    rosters = pd.DataFrame([{"full_name": "Michael Pittman", "team": "PIT", "week": 3}])
    row = latest_team_for_player("Michael Pittman Jr.", rosters)
    assert row is not None
    assert row["team"] == "PIT"


def test_data_has_suffix_query_does_not():
    rosters = pd.DataFrame([{"full_name": "Michael Pittman Jr.", "team": "PIT", "week": 3}])
    row = latest_team_for_player("Michael Pittman", rosters)
    assert row is not None
    assert row["team"] == "PIT"
