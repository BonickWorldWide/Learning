import pytest

from options_screener.models import OptionContract
from options_screener.screener import build_pop_candidate, rank_pop_candidates

BULLISH_HEADLINES = ["Company beats earnings, raises guidance", "Analyst upgrade sends shares surging"]
BEARISH_HEADLINES = ["Company misses estimates, shares plunge", "Lawsuit filed after product recall"]
UPTREND_CLOSES = [float(x) for x in range(50, 51 + 60)]  # steadily rising, 61 days
DOWNTREND_CLOSES = [float(x) for x in range(110, 49, -1)]  # steadily falling, 61 days


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
    contracts = [_otm_call(strike=60, volume=50, open_interest=1000)]  # no unusual volume
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=contracts, closes=DOWNTREND_CLOSES, headlines=BEARISH_HEADLINES, spot=51,
    )
    assert candidate.score < 0.2
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


def test_no_qualifying_contract_still_returns_a_score_and_a_note():
    # Only a near-the-money, high-delta, expensive contract available.
    pricy = _otm_call(strike=52, bid=3.00, ask=3.20, iv=0.3, dte=20)
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[pricy], closes=UPTREND_CLOSES, headlines=BULLISH_HEADLINES, spot=51,
    )
    assert candidate.picked_contracts == []
    assert any("No call found" in n for n in candidate.notes)
    assert candidate.score > 0  # the score doesn't depend on finding a contract


def test_low_confidence_sentiment_is_noted():
    candidate = build_pop_candidate(
        ticker="TST", call_contracts=[_otm_call(strike=60)], closes=UPTREND_CLOSES,
        headlines=["Company beats earnings"], spot=51,
    )
    assert any("low-confidence" in n for n in candidate.notes)


def test_rank_pop_candidates_filters_and_sorts():
    high = build_pop_candidate("HIGH", [_otm_call(60, volume=1000, open_interest=100)], UPTREND_CLOSES, BULLISH_HEADLINES, 51)
    low = build_pop_candidate("LOW", [_otm_call(60)], DOWNTREND_CLOSES, BEARISH_HEADLINES, 51)
    ranked = rank_pop_candidates([low, high], min_score=0.5)
    assert [c.ticker for c in ranked] == ["HIGH"]


def test_rank_pop_candidates_empty_when_nothing_clears_the_bar():
    low = build_pop_candidate("LOW", [_otm_call(60)], DOWNTREND_CLOSES, BEARISH_HEADLINES, 51)
    assert rank_pop_candidates([low], min_score=0.9) == []
