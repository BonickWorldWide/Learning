from cfb_matchup.continuity import build_continuity


def test_no_notes_means_no_flags():
    flags = build_continuity("Alpha")
    assert flags.has_flags is False
    assert flags.notes == []


def test_notes_are_carried_through():
    flags = build_continuity("Alpha", notes=["New head coach", "Lost starting QB to the portal"])
    assert flags.has_flags is True
    assert flags.notes == ["New head coach", "Lost starting QB to the portal"]
