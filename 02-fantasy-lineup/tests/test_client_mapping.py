from types import SimpleNamespace

from fantasy_lineup.client import player_from_box_player


def test_maps_full_box_player():
    fake = SimpleNamespace(
        name="Christian McCaffrey",
        position="RB",
        slot_position="RB",
        eligibleSlots=["RB", "RB/WR/TE", "FLEX", "BE"],
        pro_opponent="SEA",
        projected_points=18.4,
        injuryStatus="ACTIVE",
    )

    player = player_from_box_player(fake)

    assert player.name == "Christian McCaffrey"
    assert player.lineup_slot == "RB"
    assert player.eligible_slots == ["RB", "RB/WR/TE", "FLEX", "BE"]
    assert player.pro_opponent == "SEA"
    assert player.projected_points == 18.4
    assert player.injury_status == "ACTIVE"


def test_missing_optional_fields_fall_back_to_defaults():
    fake = SimpleNamespace(name="Backup Kicker", position="K", slot_position="BE")

    player = player_from_box_player(fake)

    assert player.eligible_slots == []
    assert player.pro_opponent == ""
    assert player.projected_points == 0.0
    assert player.injury_status == "ACTIVE"
