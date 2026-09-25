import json

import pytest

from cfb_matchup.bundle import games_from_bundle, load_bundle_file


def test_load_bundle_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_bundle_file(tmp_path / "nope.json")


def test_load_bundle_file_reads_json(tmp_path):
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({"team_a": "Alpha", "team_b": "Beta"}))
    data = load_bundle_file(path)
    assert data == {"team_a": "Alpha", "team_b": "Beta"}


def test_games_from_bundle_maps_fields():
    raw = [
        {
            "season": 2024, "week": 3, "date": "2024-09-21",
            "home_team": "Alpha", "away_team": "Beta",
            "home_score": 30, "away_score": 20, "neutral_site": False,
        }
    ]
    games = games_from_bundle(raw)
    assert len(games) == 1
    g = games[0]
    assert (g.season, g.week, g.home_team, g.away_team) == (2024, 3, "Alpha", "Beta")
    assert (g.home_score, g.away_score, g.neutral_site) == (30, 20, False)


def test_games_from_bundle_defaults_missing_optional_fields():
    raw = [{"season": 2024, "home_team": "Alpha", "away_team": "Beta", "home_score": 10, "away_score": 7}]
    games = games_from_bundle(raw)
    assert games[0].week == 0
    assert games[0].date == ""
    assert games[0].neutral_site is False
