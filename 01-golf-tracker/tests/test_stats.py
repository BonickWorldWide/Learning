from datetime import date

from golf_tracker.models import Round
from golf_tracker.stats import summarize


def test_summarize_empty_returns_none():
    assert summarize([]) is None


def test_summarize_computes_averages_and_extremes():
    rounds = [
        Round(course="A", par=72, strokes=90, played_on=date(2026, 1, 1)),  # +18
        Round(course="B", par=72, strokes=80, played_on=date(2026, 1, 8)),  # +8
        Round(course="C", par=71, strokes=85, played_on=date(2026, 1, 15)),  # +14
    ]

    summary = summarize(rounds)

    assert summary.rounds_played == 3
    assert summary.average_strokes == (90 + 80 + 85) / 3
    assert summary.average_to_par == (18 + 8 + 14) / 3
    assert summary.best_round.course == "B"
    assert summary.worst_round.course == "A"
