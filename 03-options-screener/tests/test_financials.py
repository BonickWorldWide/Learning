import pytest

from options_screener.financials import build_financial_growth, compute_yoy_growth, latest_and_prior_year
from options_screener.models import XbrlFact


def _fact(fy, fp, value, filed, form="10-Q"):
    return XbrlFact(fiscal_year=fy, fiscal_period=fp, value=value, form=form, filed=filed)


def test_latest_and_prior_year_matches_same_quarter_across_years():
    facts = [
        _fact(2024, "Q3", 100, "2024-10-30"),
        _fact(2025, "Q2", 130, "2025-07-30"),  # more recent by date, but wrong quarter
        _fact(2025, "Q3", 120, "2025-10-30"),
    ]
    latest, prior = latest_and_prior_year(facts)
    assert latest.value == 120
    assert prior.value == 100


def test_no_prior_year_data_returns_none_for_prior():
    facts = [_fact(2025, "Q3", 120, "2025-10-30")]
    latest, prior = latest_and_prior_year(facts)
    assert latest.value == 120
    assert prior is None


def test_empty_facts_returns_none_none():
    assert latest_and_prior_year([]) == (None, None)


def test_compute_yoy_growth_positive():
    assert compute_yoy_growth(120, 100) == pytest.approx(0.20)


def test_compute_yoy_growth_negative():
    assert compute_yoy_growth(80, 100) == pytest.approx(-0.20)


def test_compute_yoy_growth_none_when_current_missing():
    assert compute_yoy_growth(None, 100) is None


def test_compute_yoy_growth_none_when_prior_missing():
    assert compute_yoy_growth(120, None) is None


def test_compute_yoy_growth_none_when_prior_is_zero():
    assert compute_yoy_growth(120, 0) is None


def test_build_financial_growth_combines_revenue_and_eps():
    revenue_facts = [_fact(2024, "Q3", 100, "2024-10-30"), _fact(2025, "Q3", 120, "2025-10-30")]
    eps_facts = [_fact(2024, "Q3", 1.00, "2024-10-30"), _fact(2025, "Q3", 0.90, "2025-10-30")]
    growth = build_financial_growth(revenue_facts, eps_facts)
    assert growth.revenue_yoy == pytest.approx(0.20)
    assert growth.eps_yoy == pytest.approx(-0.10)
    assert growth.as_of_period == "Q3 FY2025"


def test_build_financial_growth_with_no_data_at_all():
    growth = build_financial_growth([], [])
    assert growth.revenue_yoy is None
    assert growth.eps_yoy is None
    assert growth.as_of_period is None


def test_bullish_score_both_growing_is_one():
    growth = build_financial_growth(
        [_fact(2024, "Q3", 100, "d"), _fact(2025, "Q3", 120, "d")],
        [_fact(2024, "Q3", 1.0, "d"), _fact(2025, "Q3", 1.2, "d")],
    )
    assert growth.bullish_score == pytest.approx(1.0)


def test_bullish_score_both_shrinking_is_zero():
    growth = build_financial_growth(
        [_fact(2024, "Q3", 120, "d"), _fact(2025, "Q3", 100, "d")],
        [_fact(2024, "Q3", 1.2, "d"), _fact(2025, "Q3", 1.0, "d")],
    )
    assert growth.bullish_score == pytest.approx(0.0)


def test_bullish_score_defaults_to_half_with_no_data():
    growth = build_financial_growth([], [])
    assert growth.bullish_score == pytest.approx(0.5)
