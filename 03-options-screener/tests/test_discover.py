import pytest

from options_screener.discover import prefilter_score, shortlist
from options_screener.models import MomentumResult, SentimentResult


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


def test_shortlist_sorts_highest_first():
    scored = [("LOW", 0.2), ("HIGH", 0.9), ("MID", 0.5)]
    assert shortlist(scored, top_n=3) == ["HIGH", "MID", "LOW"]


def test_shortlist_truncates_to_top_n():
    scored = [("A", 0.9), ("B", 0.8), ("C", 0.7), ("D", 0.6)]
    assert shortlist(scored, top_n=2) == ["A", "B"]


def test_shortlist_empty_input():
    assert shortlist([], top_n=15) == []
