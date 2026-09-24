from datetime import date

from golf_tracker.models import Round
from golf_tracker.storage import load_rounds, save_round


def test_load_rounds_missing_file_returns_empty(tmp_path):
    assert load_rounds(tmp_path / "rounds.json") == []


def test_save_and_load_round(tmp_path):
    data_file = tmp_path / "rounds.json"
    r = Round(course="St Andrews", par=72, strokes=84, played_on=date(2026, 6, 10))

    save_round(r, data_file)
    loaded = load_rounds(data_file)

    assert loaded == [r]


def test_save_round_appends(tmp_path):
    data_file = tmp_path / "rounds.json"
    first = Round(course="Bethpage Black", par=71, strokes=95, played_on=date(2026, 5, 1))
    second = Round(course="Torrey Pines", par=72, strokes=90, played_on=date(2026, 5, 8))

    save_round(first, data_file)
    save_round(second, data_file)

    assert load_rounds(data_file) == [first, second]
