import json

import pandas as pd
import pytest

from fantasy_lineup.manual_roster import load_roster_entries, resolve_roster


def test_load_roster_entries_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_roster_entries(tmp_path / "roster.json")


def test_load_roster_entries_reads_json(tmp_path):
    roster_file = tmp_path / "roster.json"
    roster_file.write_text(json.dumps([{"name": "Josh Allen", "position": "QB", "slot": "QB"}]))

    entries = load_roster_entries(roster_file)

    assert entries == [{"name": "Josh Allen", "position": "QB", "slot": "QB"}]


def _current_rosters():
    return pd.DataFrame(
        [{"full_name": "Josh Allen", "team": "BUF", "week": 3, "gsis_id": "00-0034857"}]
    )


def _games_df():
    return pd.DataFrame(
        [
            {"season": 2026, "week": 3, "home_team": "BUF", "away_team": "LAC", "home_score": None, "away_score": None},
        ]
    )


def test_resolve_roster_fills_in_team_and_opponent():
    entries = [{"name": "Josh Allen", "position": "QB", "slot": "QB"}]
    players = resolve_roster(entries, _current_rosters(), _games_df(), season=2026, week=3)

    assert len(players) == 1
    p = players[0]
    assert p.name == "Josh Allen"
    assert p.pro_team == "BUF"
    assert p.pro_opponent == "LAC"
    assert p.lineup_slot == "QB"


def test_resolve_roster_defaults_slot_to_bench():
    entries = [{"name": "Josh Allen", "position": "QB"}]
    players = resolve_roster(entries, _current_rosters(), _games_df(), season=2026, week=3)
    assert players[0].lineup_slot == "BE"


def test_resolve_roster_unknown_player_gets_no_team_not_a_crash():
    entries = [{"name": "Nobody Real", "position": "WR"}]
    players = resolve_roster(entries, _current_rosters(), _games_df(), season=2026, week=3)

    assert players[0].pro_team == ""
    assert players[0].pro_opponent == "BYE"


def test_resolve_roster_bye_week_marks_opponent_as_bye():
    rosters = pd.DataFrame([{"full_name": "Some Chief", "team": "KC", "week": 3, "gsis_id": "00-0000001"}])
    entries = [{"name": "Some Chief", "position": "WR"}]
    players = resolve_roster(entries, rosters, _games_df(), season=2026, week=3)
    assert players[0].pro_opponent == "BYE"
