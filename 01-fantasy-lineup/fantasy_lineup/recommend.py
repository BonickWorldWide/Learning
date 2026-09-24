from dataclasses import dataclass

from .models import PlayerWeek


@dataclass
class Swap:
    slot: str
    sit: PlayerWeek
    start: PlayerWeek
    point_gain: float


def recommend_swaps(players: list[PlayerWeek]) -> list[Swap]:
    """Suggest bench players who are projected to outscore a starter in their slot.

    Greedy by roster order: each starter is matched against the best still-unused,
    slot-eligible bench player. A bench player is only ever suggested for one slot.
    """
    starters = [p for p in players if not p.is_bench]
    bench = [p for p in players if p.is_bench]

    used_bench_names: set[str] = set()
    swaps: list[Swap] = []

    for starter in starters:
        candidates = [
            b
            for b in bench
            if b.name not in used_bench_names
            and starter.lineup_slot in b.eligible_slots
            and b.projected_points > starter.projected_points
        ]
        if not candidates:
            continue

        best = max(candidates, key=lambda p: p.projected_points)
        used_bench_names.add(best.name)
        swaps.append(
            Swap(
                slot=starter.lineup_slot,
                sit=starter,
                start=best,
                point_gain=best.projected_points - starter.projected_points,
            )
        )

    swaps.sort(key=lambda s: s.point_gain, reverse=True)
    return swaps
