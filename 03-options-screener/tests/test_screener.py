import pytest

from options_screener.models import FinancialGrowth, OptionContract
from options_screener.screener import build_pop_candidate, rank_pop_candidates

BULLISH_HEADLINES = ["Company beats earnings, raises guidance", "Analyst upgrade sends shares surging"]
BEARISH_HEADLINES = ["Company misses estimates, shares plunge", "Lawsuit filed after product recall"]


def _zigzag(start: float, up_mult: float, down_mult: float, days: int) -> list[float]:
    """A deterministic, noisy-but-directional price series -- real daily
    swings (not a smooth ramp) netting to a clear trend over `days`. A
    plain `range()` ramp (the original fixture here) has almost no real
    day-to-day variance, which reads as essentially zero realized
    volatility -- it accidentally tripped the new min_realized_volatility
    floor in screener.build_pop_candidate and made every "bullish momentum"
    fixture also read as "too calm to ever pick a contract." Real alternating
    moves keep the exact same net direction (so every momentum assertion
    below is unchanged) while giving the volatility signal something
    realistic to compute.
    """
    closes = [start]
    for i in range(days):
        closes.append(closes[-1] * (up_mult if i % 2 == 0 else down_mult))
    return closes


# Both net strongly in their named direction (bullish_score 1.0 / 0.0) and
# both clear the default movement_score_ceiling (0.80 annualized realized
# vol) outright, so "all signals maxed" fixtures still mean exactly that.
UPTREND_CLOSES = _zigzag(50.0, 1.10, 0.98, 60)
DOWNTREND_CLOSES = _zigzag(110.0, 0.90, 1.02, 60)


def _otm_call(strike, volume=50, open_interest=500, iv=0.5, dte=30, bid=0.30, ask=0.50):
    return OptionContract(
        ticker="TST", option_type="call", strike=strike, expiry="2026-01-01", days_to_expiry=dte,
        bid=bid, ask=ask, last_price=(bid + ask) / 2, volume=volume, open_interest=open_interest,
        implied_volatility=iv,
    )


def test_bullish_signals_score_high():
    contracts = [_otm_call(strike=60, volume=1000, open_interest=100)]  # unusual volume too
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=contracts, closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert candidate.score > 0.8
    assert candidate.components["momentum"] == pytest.approx(1.0)
    assert candidate.unusual_contracts != []


def test_bearish_signals_score_low():
    # "movement" (realized volatility), "jump_risk" (large_move_frequency)
    # and "iv_value" are all deliberately direction-agnostic -- a stock
    # crashing hard is still moving a lot, still gapping hard, and the
    # test contract's fixed 50% IV still reads as cheap against that much
    # realized volatility, regardless of which way the stock is going. The
    # three directional/event components (momentum, sentiment,
    # unusual_volume) are still all 0.0; movement, jump_risk and iv_value
    # all read 1.0, so the six-way average lands at 3/6 = 0.5 rather than
    # close to zero the way a 3-way average of all-zero would.
    contracts = [_otm_call(strike=60, volume=50, open_interest=1000)]  # no unusual volume
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=contracts, closes=DOWNTREND_CLOSES, headlines=BEARISH_HEADLINES, spot=51,
    )
    assert candidate.score == pytest.approx(0.5)
    assert candidate.components["momentum"] == pytest.approx(0.0)


def test_picks_a_contract_in_the_delta_band_and_under_max_premium():
    # A deep-OTM cheap call and a near-the-money expensive one -- only the
    # deep-OTM one should land in a 0.10-0.30 delta band under $1.
    cheap_far_otm = _otm_call(strike=58, bid=0.30, ask=0.50, iv=0.6, dte=20)  # delta ~0.20
    near_money_pricy = _otm_call(strike=52, bid=3.00, ask=3.20, iv=0.3, dte=20)  # delta ~0.42
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[cheap_far_otm, near_money_pricy], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.10, 0.30), max_premium=1.00,
    )
    assert len(candidate.picked_contracts) == 1
    picked_contract, picked_greeks = candidate.picked_contracts[0]
    assert picked_contract.strike == 58
    assert 0.10 <= picked_greeks.delta <= 0.30


def test_picked_contracts_favor_higher_delta_over_cheaper_price():
    # Both qualify (in-band, under cap) -- a real run showed the pick
    # defaulted to whichever was merely cheaper, which meant the headline
    # pick was consistently the deepest, least-likely-to-actually-pop
    # contract in the band. The higher-delta one (closer to landing in the
    # money) should be picked first even though it costs a bit more.
    cheaper_deeper = _otm_call(strike=62, bid=0.10, ask=0.20, iv=0.6, dte=20)  # lower delta, cheaper
    pricier_closer = _otm_call(strike=57, bid=0.60, ask=0.80, iv=0.6, dte=20)  # higher delta, still under cap
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[cheaper_deeper, pricier_closer], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.05, 0.35), max_premium=1.00,
    )
    assert len(candidate.picked_contracts) == 2
    first_contract, first_greeks = candidate.picked_contracts[0]
    assert first_contract.strike == 57
    second_contract, _ = candidate.picked_contracts[1]
    assert second_contract.strike == 62
    assert first_greeks.delta > candidate.picked_contracts[1][1].delta


def test_no_qualifying_contract_still_returns_a_score_and_a_note():
    # Only a near-the-money, high-delta contract available -- its delta
    # (~0.42) is above the band entirely, not just too expensive.
    pricy = _otm_call(strike=52, bid=3.00, ask=3.20, iv=0.3, dte=20)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[pricy], closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert candidate.picked_contracts == []
    assert any("at all, regardless of price" in n for n in candidate.notes)
    assert candidate.score > 0  # the score doesn't depend on finding a contract


def test_in_band_but_too_expensive_reports_the_cheapest_real_price():
    # A real run showed this is the actual common case: a delta-band
    # contract exists, it's just pricier than the cost cap -- the note
    # should say exactly what it would cost, not just "no pick."
    in_band_but_pricey = _otm_call(strike=58, bid=3.00, ask=3.20, iv=0.6, dte=20)  # delta ~0.20, real cost ~$310
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[in_band_but_pricey], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.10, 0.30), max_premium=0.30,
    )
    assert candidate.picked_contracts == []
    assert any("cheapest costs $3.10/share" in n for n in candidate.notes)
    assert any("Raise pop_max_contract_cost to at least $310" in n for n in candidate.notes)


def test_low_confidence_sentiment_is_noted():
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(strike=60)], closes=UPTREND_CLOSES,
        headlines=["Company beats earnings"], spot=51,
    )
    assert any("low-confidence" in n for n in candidate.notes)


def test_rank_pop_candidates_filters_and_sorts():
    # LOW now scores exactly 0.5 (see test_bearish_signals_score_low), so
    # the bar has to clear that to still test real filtering.
    high = build_pop_candidate("HIGH", [_otm_call(60, volume=1000, open_interest=100)], UPTREND_CLOSES, BULLISH_HEADLINES, 51)
    low = build_pop_candidate("LOW", [_otm_call(60)], DOWNTREND_CLOSES, BEARISH_HEADLINES, 51)
    ranked = rank_pop_candidates([low, high], min_score=0.6)
    assert [c.ticker for c in ranked] == ["HIGH"]


def test_rank_pop_candidates_empty_when_nothing_clears_the_bar():
    low = build_pop_candidate("LOW", [_otm_call(60)], DOWNTREND_CLOSES, BEARISH_HEADLINES, 51)
    assert rank_pop_candidates([low], min_score=0.9) == []


def test_near_expiry_contract_is_excluded_from_the_delta_band_pick():
    # A real run found zero picks across 15 tickers because every nearest
    # expiry was 2-3 days out -- at that range delta collapses toward zero
    # a percent or two from the strike, so a contract that would otherwise
    # qualify (same strike/iv as the passing test above) must not be picked
    # once it's too close to expiry.
    near_expiry = _otm_call(strike=58, bid=0.30, ask=0.50, iv=0.6, dte=3)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[near_expiry], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.10, 0.30), max_premium=1.00,
        min_days_to_expiry=7,
    )
    assert candidate.picked_contracts == []
    assert any("0 eligible" in n for n in candidate.notes)


def test_near_expiry_contract_is_excluded_from_the_unusual_volume_check():
    near_expiry = _otm_call(strike=60, volume=1000, open_interest=100, dte=2)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[near_expiry], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, min_days_to_expiry=7,
    )
    assert candidate.unusual_contracts == []
    assert candidate.components["unusual_volume"] == 0.0


def test_min_days_to_expiry_defaults_to_seven():
    near_expiry = _otm_call(strike=58, bid=0.30, ask=0.50, iv=0.6, dte=5)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[near_expiry], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.10, 0.30), max_premium=1.00,
    )
    assert candidate.picked_contracts == []


def test_financial_growth_omitted_keeps_the_three_way_average():
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(60)], closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert "financial_growth" not in candidate.components
    assert candidate.financial_growth is None


def test_financial_growth_included_becomes_a_fifth_equal_weighted_vote():
    growing = FinancialGrowth(revenue_yoy=0.15, eps_yoy=0.10, as_of_period="Q3 FY2025")
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(60, volume=1000, open_interest=100)], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, financial_growth=growing,
    )
    assert candidate.components["financial_growth"] == pytest.approx(1.0)
    # all five signals bullish/maxed here (including movement, since
    # UPTREND_CLOSES clears the default movement_score_ceiling outright)
    # -> the average should still be 1.0
    assert candidate.score == pytest.approx(1.0)
    assert candidate.financial_growth is growing


def test_financial_growth_with_no_data_votes_neutral_and_is_noted():
    empty_growth = FinancialGrowth(revenue_yoy=None, eps_yoy=None, as_of_period=None)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(60)], closes=UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, financial_growth=empty_growth,
    )
    assert candidate.components["financial_growth"] == pytest.approx(0.5)
    assert any("No SEC financial data" in n for n in candidate.notes)


# --- Realized volatility: a hard floor, not just another vote ---

# A smooth, essentially flat series -- the kind of "barely moves" stock a
# real run kept surfacing far-OTM calls on. Clears every momentum signal
# (it's a steady uptrend) but has almost no real day-to-day variance.
CALM_UPTREND_CLOSES = [50.0 + 0.05 * i for i in range(61)]


def test_a_too_calm_stock_never_gets_a_picked_contract():
    # Same contract shape as test_picks_a_contract_in_the_delta_band_...,
    # which *does* get a pick on the noisy UPTREND_CLOSES fixture -- the
    # only thing different here is the stock itself barely moves.
    cheap_far_otm = _otm_call(strike=58, bid=0.30, ask=0.50, iv=0.6, dte=20)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[cheap_far_otm], closes=CALM_UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.10, 0.30), max_premium=1.00,
    )
    assert candidate.picked_contracts == []
    assert any("doesn't move enough" in n for n in candidate.notes)
    assert any("Realized volatility is only" in n for n in candidate.notes)
    # The score itself is still computed -- a calm stock isn't hidden,
    # just never handed a contract to buy.
    assert candidate.score > 0


def test_min_realized_volatility_is_a_real_knob_not_hardcoded():
    # The exact same calm stock, with the floor turned all the way down --
    # should get the same pick a noisy stock would.
    cheap_far_otm = _otm_call(strike=58, bid=0.30, ask=0.50, iv=0.6, dte=20)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[cheap_far_otm], closes=CALM_UPTREND_CLOSES,
        headlines=BULLISH_HEADLINES, spot=51, delta_range=(0.10, 0.30), max_premium=1.00,
        min_realized_volatility=0.0,
    )
    assert len(candidate.picked_contracts) == 1


def test_movement_component_present_and_omitted_appropriately():
    with_history = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(60)], closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert "movement" in with_history.components
    assert with_history.realized_volatility is not None

    too_short = [50.0, 51.0, 52.0]  # nowhere near volatility.REALIZED_VOL_WINDOW + 1
    without_history = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(60)], closes=too_short, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert "movement" not in without_history.components
    assert without_history.realized_volatility is None


def test_stock_volume_component_elevated_vs_normal():
    contracts = [_otm_call(60)]
    elevated = [1_000_000] * 20 + [5_000_000] * 5  # 5x baseline
    normal = [1_000_000] * 25

    elevated_candidate = build_pop_candidate(
        ticker="TST", call_contracts=contracts, closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
        volumes=elevated,
    )
    normal_candidate = build_pop_candidate(
        ticker="TST", call_contracts=contracts, closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
        volumes=normal,
    )
    assert elevated_candidate.components["stock_volume"] == 1.0
    assert normal_candidate.components["stock_volume"] == 0.0
    assert elevated_candidate.relative_volume == pytest.approx(5.0)


def test_stock_volume_component_omitted_without_volume_data():
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(60)], closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert "stock_volume" not in candidate.components
    assert candidate.relative_volume is None
