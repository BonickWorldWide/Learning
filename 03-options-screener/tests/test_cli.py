import pytest

from options_screener.cli import _rationale, _top_picks
from options_screener.models import Greeks, MomentumResult, OptionContract, PopCandidate, SentimentResult


def _candidate(ticker, score, components, picked_contracts=(), headline_count=5):
    return PopCandidate(
        ticker=ticker,
        score=score,
        components=components,
        momentum=MomentumResult(return_20d=0.05, rsi_14=60, above_50sma=True),
        sentiment=SentimentResult(score=0.2, headline_count=headline_count),
        unusual_contracts=[],
        picked_contracts=list(picked_contracts),
        notes=[],
    )


def _contract(strike, mid, dte=20):
    bid = mid - 0.01
    ask = mid + 0.01
    return OptionContract(
        ticker="TST", option_type="call", strike=strike, expiry="2026-01-01", days_to_expiry=dte,
        bid=bid, ask=ask, last_price=mid, volume=100, open_interest=100, implied_volatility=0.4,
    )


def _greeks(delta):
    return Greeks(delta=delta, gamma=0.01, theta=-0.01, vega=0.05, fair_value=1.0)


def test_rationale_always_shows_the_numeric_breakdown():
    # A real run's "Why" line dropped a moderate (neither strong nor weak)
    # sentiment score entirely, which read as "sentiment wasn't used" even
    # though it was a real third of the average. The actual number must
    # always be visible, not just the strong/weak label.
    cand = _candidate("TST", 0.75, {"momentum": 0.67, "sentiment": 0.59, "unusual_volume": 1.00})
    text = _rationale(cand)
    assert "sentiment 0.59" in text
    assert "momentum 0.67" in text
    assert "unusual volume 1.00" in text


def test_rationale_still_calls_out_strong_and_weak_components():
    cand = _candidate("TST", 0.5, {"momentum": 1.0, "sentiment": 0.1})
    text = _rationale(cand)
    assert "strong momentum" in text
    assert "weak sentiment" in text


def test_rationale_notes_low_confidence_sentiment():
    cand = _candidate("TST", 0.6, {"momentum": 0.6}, headline_count=1)
    assert "sentiment unconfirmed" in _rationale(cand)


def test_top_picks_prefers_higher_delta_over_cheaper_price_as_tiebreak():
    # Same score for both tickers -- a real run's tiebreak (cheapest price)
    # meant the headline pick was always the deepest, least-likely-to-pop
    # contract available. Delta (probability of actually landing in the
    # money) should decide ties instead.
    cheap_deep = _candidate("CHEAP", 0.8, {}, picked_contracts=[(_contract(75, 0.10), _greeks(0.10))])
    pricier_closer = _candidate("CLOSER", 0.8, {}, picked_contracts=[(_contract(65, 0.24), _greeks(0.15))])
    top = _top_picks([cheap_deep, pricier_closer])
    assert top[0][0].ticker == "CLOSER"
    assert top[1][0].ticker == "CHEAP"


def test_top_picks_sorts_by_score_first():
    low_score = _candidate("LOW", 0.6, {}, picked_contracts=[(_contract(65, 0.24), _greeks(0.30))])
    high_score = _candidate("HIGH", 0.9, {}, picked_contracts=[(_contract(75, 0.10), _greeks(0.10))])
    top = _top_picks([low_score, high_score])
    assert top[0][0].ticker == "HIGH"


def test_top_picks_drops_candidates_with_nothing_picked():
    no_pick = _candidate("NOPE", 0.9, {}, picked_contracts=[])
    has_pick = _candidate("YES", 0.7, {}, picked_contracts=[(_contract(65, 0.24), _greeks(0.15))])
    top = _top_picks([no_pick, has_pick])
    assert len(top) == 1
    assert top[0][0].ticker == "YES"
