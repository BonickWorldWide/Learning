from datetime import date

from golf_tracker.models import Round


def test_to_par():
    r = Round(course="Pebble Beach", par=72, strokes=88, played_on=date(2026, 9, 20))
    assert r.to_par == 16


def test_round_trip_dict():
    original = Round(course="Augusta National", par=72, strokes=79, played_on=date(2026, 4, 1))
    restored = Round.from_dict(original.to_dict())
    assert restored == original
