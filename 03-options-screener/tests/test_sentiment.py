import pytest

from options_screener.sentiment import score_headlines


def test_all_positive_headlines_score_near_one():
    headlines = ["Company beats earnings expectations, raises guidance", "Analyst upgrade sends shares surging"]
    result = score_headlines(headlines)
    assert result.score == pytest.approx(1.0)
    assert result.headline_count == 2
    assert len(result.positive_headlines) == 2
    assert result.negative_headlines == []


def test_all_negative_headlines_score_near_minus_one():
    headlines = ["Company misses estimates, shares plunge", "Lawsuit filed after product recall"]
    result = score_headlines(headlines)
    assert result.score == pytest.approx(-1.0)
    assert len(result.negative_headlines) == 2


def test_mixed_headlines_average_out():
    headlines = ["Company beats earnings", "Company faces lawsuit"]
    result = score_headlines(headlines)
    assert result.score == pytest.approx(0.0)


def test_neutral_headline_with_no_lexicon_hits_scores_zero():
    result = score_headlines(["Company to present at investor conference"])
    assert result.score == pytest.approx(0.0)


def test_empty_headlines_list():
    result = score_headlines([])
    assert result.score == 0.0
    assert result.headline_count == 0
    assert result.low_confidence is True


def test_low_confidence_below_three_headlines():
    result = score_headlines(["Company beats earnings"])
    assert result.headline_count == 1
    assert result.low_confidence is True


def test_not_low_confidence_at_three_or_more():
    headlines = ["Company beats earnings", "Shares gain", "Analyst optimistic"]
    result = score_headlines(headlines)
    assert result.low_confidence is False


def test_scoring_is_case_insensitive():
    result = score_headlines(["COMPANY BEATS EXPECTATIONS"])
    assert result.score > 0
