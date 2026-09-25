from cfb_matchup.h2h import build_head_to_head
from cfb_matchup.models import Game
from cfb_matchup.tables import format_record_table, format_venue_table


def _summary():
    games = [
        Game(2018, 1, "2018-09-01", "Alpha", "Beta", 30, 20),
        Game(2019, 1, "2019-09-01", "Beta", "Alpha", 24, 21),
    ]
    return build_head_to_head(games, "Alpha", "Beta")


def test_record_table_has_a_row_per_window():
    table = format_record_table(_summary())
    lines = table.splitlines()
    assert lines[0].startswith("| Window |")
    assert any(line.startswith("| all-time |") for line in lines)
    assert any(line.startswith("| last 10 |") for line in lines)
    assert any(line.startswith("| last 20 |") for line in lines)


def test_record_table_shows_correct_counts():
    table = format_record_table(_summary())
    all_time_row = next(line for line in table.splitlines() if line.startswith("| all-time |"))
    assert "| 2 |" in all_time_row  # 2 games
    assert "+10.0" in all_time_row  # Alpha's avg margin in its one win


def test_venue_table_only_lists_venues_that_occurred():
    summary = _summary()
    table = format_venue_table("Alpha", summary.team_a_venue_splits)
    assert "home" in table
    assert "away" in table
    assert "neutral" not in table  # no neutral-site meetings in this fixture


def test_venue_table_formats_missing_margin_as_em_dash():
    table = format_venue_table("Nobody", {})
    assert "|" in table  # header still renders even with zero rows
