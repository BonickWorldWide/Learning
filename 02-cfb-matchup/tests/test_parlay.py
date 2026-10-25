import pytest

from cfb_matchup.parlay import (
    LegEdge,
    american_to_decimal,
    combined_decimal_odds,
    combined_probability,
    leg_edges,
    parlay_ev,
    parlay_payout,
)


def test_american_to_decimal_favorite():
    assert american_to_decimal(-230) == pytest.approx(1 + 100 / 230)


def test_american_to_decimal_underdog():
    assert american_to_decimal(150) == pytest.approx(1 + 150 / 100)


def test_american_to_decimal_even_money():
    assert american_to_decimal(100) == pytest.approx(2.0)


def test_combined_decimal_odds_matches_hand_calc():
    # A real 5-leg slip: UCLA -650, Georgia Tech -230, South Carolina -135,
    # Minnesota -115, UCF -110.
    odds = [-650, -230, -135, -115, -110]
    expected = 1.0
    for o in odds:
        expected *= american_to_decimal(o)
    assert combined_decimal_odds(odds) == pytest.approx(expected)
    assert combined_decimal_odds(odds) == pytest.approx(10.286, abs=0.01)


def test_combined_decimal_odds_single_leg_is_that_legs_own_decimal():
    assert combined_decimal_odds([-110]) == pytest.approx(american_to_decimal(-110))


def test_combined_probability_matches_hand_calc():
    probs = [0.867, 0.697, 0.574, 0.535, 0.524]
    expected = 0.867 * 0.697 * 0.574 * 0.535 * 0.524
    assert combined_probability(probs) == pytest.approx(expected)


def test_combined_probability_drops_fast_with_more_legs():
    # Five independent 70% legs combine to well under half of any one leg's
    # own probability -- this is the core "going 4 of 5 is still a total
    # loss" mechanism.
    five_legs = combined_probability([0.70] * 5)
    assert five_legs == pytest.approx(0.70**5)
    assert five_legs < 0.70 / 4


def test_combined_probability_empty_is_one():
    # No legs means nothing to multiply -- the identity element, not an
    # error, so callers never have to special-case an empty ticket.
    assert combined_probability([]) == 1.0


def test_parlay_payout_matches_hand_calc():
    odds = [-650, -230, -135, -115, -110]
    assert parlay_payout(odds, stake=5.0) == pytest.approx(5.0 * combined_decimal_odds(odds))
    assert parlay_payout(odds, stake=5.0) == pytest.approx(51.43, abs=0.01)


def test_parlay_ev_near_zero_at_exactly_market_implied_probabilities():
    # Each leg priced with zero individual edge -- the combined ticket
    # should also have ~zero EV, same as any single fair-priced bet.
    odds = [-230, -110]
    probs = [230 / 330, 110 / 210]  # exactly the market-implied probabilities
    assert parlay_ev(probs, odds, stake=5.0) == pytest.approx(0.0, abs=0.01)


def test_parlay_ev_positive_when_every_leg_has_real_edge():
    odds = [-230, -110]
    market_implied = [230 / 330, 110 / 210]
    better = [p + 0.08 for p in market_implied]  # a real edge on both legs
    assert parlay_ev(better, odds, stake=5.0) > 0


def test_parlay_ev_negative_when_legs_are_overpriced():
    odds = [-230, -110]
    market_implied = [230 / 330, 110 / 210]
    worse = [p - 0.08 for p in market_implied]
    assert parlay_ev(worse, odds, stake=5.0) < 0


def test_parlay_ev_scales_with_stake():
    odds = [-150, 120]
    probs = [0.65, 0.5]
    ev_5 = parlay_ev(probs, odds, stake=5.0)
    ev_50 = parlay_ev(probs, odds, stake=50.0)
    assert ev_50 == pytest.approx(ev_5 * 10)


def test_leg_edges_matches_hand_calc():
    odds = [-230, -110]
    probs = [0.75, 0.60]  # real edge over both market prices
    edges = leg_edges(probs, odds)
    assert len(edges) == 2
    by_index = {e.index: e for e in edges}
    assert by_index[0].edge == pytest.approx(0.75 - 230 / 330)
    assert by_index[1].edge == pytest.approx(0.60 - 110 / 210)


def test_leg_edges_sorted_worst_first():
    odds = [-110, -110, -110]
    probs = [0.60, 0.50, 0.70]  # edges: +0.076, -0.024, +0.176 roughly
    edges = leg_edges(probs, odds)
    assert [e.index for e in edges] == [1, 0, 2]
    assert edges[0].edge < edges[1].edge < edges[2].edge


def test_leg_edges_zero_or_negative_edge_is_a_drop_candidate():
    # A leg priced exactly at the model's own confidence (or worse) -- the
    # real-world shape of a leg that adds pure bust risk for free.
    odds = [-110]
    probs = [110 / 210]  # exactly market-implied, zero edge
    edge = leg_edges(probs, odds)[0]
    assert edge.edge == pytest.approx(0.0, abs=1e-9)


def test_leg_edge_is_a_dataclass_with_a_computed_edge_property():
    e = LegEdge(index=0, model_prob=0.7, market_implied_prob=0.6)
    assert e.edge == pytest.approx(0.1)
