from types import SimpleNamespace

from fantasy_lineup.client import player_from_box_player


def test_maps_full_box_player():
    fake = SimpleNamespace(
        playerId=4239992,
        name="Christian McCaffrey",
        position="RB",
        slot_position="RB",
        proTeam="SF",
        pro_opponent="SEA",
    )

    player = player_from_box_player(fake)

    assert player.espn_id == "4239992"
    assert player.name == "Christian McCaffrey"
    assert player.lineup_slot == "RB"
    assert player.pro_team == "SF"
    assert player.pro_opponent == "SEA"


def test_missing_optional_fields_fall_back_to_defaults():
    fake = SimpleNamespace(name="Backup Kicker", position="K", slot_position="BE")

    player = player_from_box_player(fake)

    assert player.espn_id == ""
    assert player.pro_team == ""
    assert player.pro_opponent == ""
