from dataclasses import dataclass

from .models import Round


@dataclass
class Summary:
    rounds_played: int
    average_strokes: float
    average_to_par: float
    best_round: Round
    worst_round: Round


def summarize(rounds: list[Round]) -> Summary | None:
    if not rounds:
        return None

    total_strokes = sum(r.strokes for r in rounds)
    total_to_par = sum(r.to_par for r in rounds)
    best = min(rounds, key=lambda r: r.to_par)
    worst = max(rounds, key=lambda r: r.to_par)

    return Summary(
        rounds_played=len(rounds),
        average_strokes=total_strokes / len(rounds),
        average_to_par=total_to_par / len(rounds),
        best_round=best,
        worst_round=worst,
    )
