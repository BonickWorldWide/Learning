from fantasy_lineup.scoring import fantasy_points


def test_rb_stat_line_ppr():
    stats = {"rushing_yards": 100, "rushing_tds": 1, "receptions": 3, "receiving_yards": 20}
    # 100*0.1 + 1*6 + 3*1 (ppr) + 20*0.1 = 10 + 6 + 3 + 2 = 21
    assert fantasy_points(stats, "ppr") == 21.0


def test_rb_stat_line_standard_has_no_reception_bonus():
    stats = {"rushing_yards": 100, "rushing_tds": 1, "receptions": 3, "receiving_yards": 20}
    # same as above minus the 3 PPR points
    assert fantasy_points(stats, "standard") == 18.0


def test_half_ppr_is_between_standard_and_ppr():
    stats = {"receptions": 4}
    assert fantasy_points(stats, "half_ppr") == 2.0


def test_qb_stat_line_with_interception():
    stats = {"passing_yards": 300, "passing_tds": 3, "interceptions": 2}
    # 300*0.04 + 3*4 - 2*2 = 12 + 12 - 4 = 20
    assert fantasy_points(stats, "ppr") == 20.0


def test_missing_stats_default_to_zero():
    assert fantasy_points({}, "ppr") == 0.0


def test_unknown_scoring_falls_back_to_ppr():
    stats = {"receptions": 1}
    assert fantasy_points(stats, "not_a_real_scoring_type") == 1.0
