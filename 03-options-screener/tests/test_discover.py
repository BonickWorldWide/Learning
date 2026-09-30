import pytest

from options_screener.discover import affordability_score, prefilter_score, shortlist
from options_screener.models import MomentumResult, SentimentResult

# A $30 cap with a 0.10-0.30 delta band, 7 days to expiry -- the same shape
# as the real config that produced zero picks across every shortlisted
# ticker in a live run, because the prefilter shortlisted $200-400+ stocks
# by momentum alone. Verified against actual black_scholes_greeks output
# (see discover.py's docstring for the real numbers): at the assumed 35%
# IV, a $20 stock's 0.20-delta call costs ~$10.58/contract (comfortably
# under cap, score 1.0), a $100 stock's costs ~$52.89 (score ~0.567), and a
# $400 stock's costs ~$211.56 (score ~0.142).
CAP = 30.0
DELTA_RANGE = (0.10, 0.30)
DTE = 7


def test_affordability_score_cheap_stock_is_fully_affordable():
    assert affordability_score(spot=20, cost_cap=CAP, delta_range=DELTA_RANGE, min_days_to_expiry=DTE) == pytest.approx(1.0)


def test_affordability_score_expensive_stock_scores_much_lower():
    score = affordability_score(spot=400, cost_cap=CAP, delta_range=DELTA_RANGE, min_days_to_expiry=DTE)
    assert score == pytest.approx(30 / 211.56, abs=0.01)


def test_affordability_score_decreases_as_spot_price_rises():
    scores = [
        affordability_score(spot=spot, cost_cap=CAP, delta_range=DELTA_RANGE, min_days_to_expiry=DTE)
        for spot in (20, 100, 200, 400)
    ]
    assert scores == sorted(scores, reverse=True)


def test_affordability_score_never_exceeds_one():
    # A very cheap stock's estimated contract cost is a few cents -- the
    # score is capped at 1.0 rather than reporting something like 40x.
    assert affordability_score(spot=1, cost_cap=CAP, delta_range=DELTA_RANGE, min_days_to_expiry=DTE) == 1.0


def test_affordability_score_is_a_soft_downweight_not_a_hard_exclusion():
    # Even a $400 stock still gets a positive, non-zero score -- a stock
    # with exceptional momentum and sentiment can still outscore an
    # affordable-but-flat one. This isn't a hard price cutoff.
    score = affordability_score(spot=400, cost_cap=CAP, delta_range=DELTA_RANGE, min_days_to_expiry=DTE)
    assert 0.0 < score < 1.0


def test_prefilter_score_with_affordability_downweights_expensive_stocks():
    # Same momentum for both -- only affordability should separate them.
    momentum = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)
    cheap_stock_score = prefilter_score(momentum, affordability=1.0)
    expensive_stock_score = prefilter_score(momentum, affordability=0.14)
    assert cheap_stock_score > expensive_stock_score


def test_prefilter_score_with_no_affordability_matches_explicit_none():
    # Existing callers (and the tests above this one) that only pass
    # momentum/sentiment must be unaffected by affordability existing --
    # it's optional, appended only when present, not a hidden third
    # component defaulting to some neutral value.
    momentum = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)
    assert prefilter_score(momentum) == prefilter_score(momentum, affordability=None)


def test_prefilter_score_bullish_momentum_and_sentiment():
    momentum = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)  # bullish_score 1.0
    sentiment = SentimentResult(score=1.0, headline_count=5)  # rescales to 1.0
    assert prefilter_score(momentum, sentiment) == pytest.approx(1.0)


def test_prefilter_score_bearish_momentum_and_sentiment():
    momentum = MomentumResult(return_20d=-0.1, rsi_14=30, above_50sma=False)  # bullish_score 0.0
    sentiment = SentimentResult(score=-1.0, headline_count=5)  # rescales to 0.0
    assert prefilter_score(momentum, sentiment) == pytest.approx(0.0)


def test_prefilter_score_mixed_signals_average_out():
    momentum = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)  # 1.0
    sentiment = SentimentResult(score=-1.0, headline_count=5)  # 0.0
    assert prefilter_score(momentum, sentiment) == pytest.approx(0.5)


def test_prefilter_score_with_no_sentiment_treats_it_as_neutral():
    # The real prefilter loop doesn't fetch news at all (see discover.py's
    # docstring) -- omitting sentiment entirely must score identically to
    # an explicitly neutral one.
    momentum = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)  # 1.0
    neutral = SentimentResult(score=0.0, headline_count=0)
    assert prefilter_score(momentum) == prefilter_score(momentum, neutral)


def test_prefilter_score_without_sentiment_ranks_purely_by_momentum():
    # A neutral sentiment adds the same constant to every ticker, so two
    # tickers with different momentum must still rank in momentum's order
    # even with no sentiment data at all.
    strong = MomentumResult(return_20d=0.1, rsi_14=70, above_50sma=True)
    weak = MomentumResult(return_20d=-0.1, rsi_14=30, above_50sma=False)
    assert prefilter_score(strong) > prefilter_score(weak)


def test_shortlist_sorts_highest_first():
    scored = [("LOW", 0.2), ("HIGH", 0.9), ("MID", 0.5)]
    assert shortlist(scored, top_n=3) == ["HIGH", "MID", "LOW"]


def test_shortlist_truncates_to_top_n():
    scored = [("A", 0.9), ("B", 0.8), ("C", 0.7), ("D", 0.6)]
    assert shortlist(scored, top_n=2) == ["A", "B"]


def test_shortlist_empty_input():
    assert shortlist([], top_n=15) == []
