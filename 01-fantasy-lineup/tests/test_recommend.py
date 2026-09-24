from fantasy_lineup.models import PlayerWeek
from fantasy_lineup.recommend import recommend_swaps


def rb(name: str, slot: str, proj: float, opp: str = "OPP") -> PlayerWeek:
    return PlayerWeek(
        name=name,
        position="RB",
        lineup_slot=slot,
        eligible_slots=["RB", "FLEX", "BE"],
        pro_opponent=opp,
        projected_points=proj,
    )


def test_no_swap_when_starters_already_best():
    players = [rb("Starter", "RB", 15.0), rb("Bench", "BE", 10.0)]
    assert recommend_swaps(players) == []


def test_recommends_swap_when_bench_outprojects_starter():
    starter = rb("Weak Starter", "RB", 8.0)
    bench = rb("Strong Bench", "BE", 14.0)

    swaps = recommend_swaps([starter, bench])

    assert len(swaps) == 1
    swap = swaps[0]
    assert swap.slot == "RB"
    assert swap.sit.name == "Weak Starter"
    assert swap.start.name == "Strong Bench"
    assert swap.point_gain == 6.0


def test_bench_player_ineligible_for_slot_is_ignored():
    starter = PlayerWeek("QB Starter", "QB", "QB", ["QB", "BE"], "OPP", 18.0)
    ineligible_bench = rb("RB Bench", "BE", 25.0)

    assert recommend_swaps([starter, ineligible_bench]) == []


def test_each_bench_player_used_at_most_once():
    starter_a = rb("Starter A", "RB", 5.0)
    starter_b = PlayerWeek("Starter B", "RB", "FLEX", ["RB", "FLEX", "BE"], "OPP", 6.0)
    bench = rb("Best Bench", "BE", 20.0)

    swaps = recommend_swaps([starter_a, starter_b, bench])

    assert len(swaps) == 1
    assert swaps[0].sit.name == "Starter A"


def test_swaps_sorted_by_point_gain_descending():
    # Non-overlapping slots (QB vs TE) so each starter can only be matched
    # against its own bench player — isolates sort order from the greedy
    # matching, which is covered by test_each_bench_player_used_at_most_once.
    small_gain_starter = PlayerWeek("Small Gain Starter", "QB", "QB", ["QB", "BE"], "OPP", 10.0)
    small_gain_bench = PlayerWeek("Small Gain Bench", "QB", "BE", ["QB", "BE"], "OPP", 11.0)
    big_gain_starter = PlayerWeek("Big Gain Starter", "TE", "TE", ["TE", "BE"], "OPP", 4.0)
    big_gain_bench = PlayerWeek("Big Gain Bench", "TE", "BE", ["TE", "BE"], "OPP", 18.0)

    swaps = recommend_swaps(
        [small_gain_starter, big_gain_starter, small_gain_bench, big_gain_bench]
    )

    assert [s.sit.name for s in swaps] == ["Big Gain Starter", "Small Gain Starter"]
