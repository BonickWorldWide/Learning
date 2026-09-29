from .models import FinancialGrowth, XbrlFact


def latest_and_prior_year(facts: list[XbrlFact]) -> tuple[XbrlFact | None, XbrlFact | None]:
    """The most recently reported fact, and the one from the same fiscal
    period a year earlier -- Q3 compared to last year's Q3, never to this
    year's Q2, so a seasonal business isn't misread as growing or
    shrinking just because one quarter is bigger than another by design.
    (None, None) if there's nothing to compare, or nothing at all.
    """
    if not facts:
        return None, None

    latest = max(facts, key=lambda f: (f.fiscal_year, f.filed))
    same_period_prior_year = [
        f for f in facts if f.fiscal_period == latest.fiscal_period and f.fiscal_year == latest.fiscal_year - 1
    ]
    prior = max(same_period_prior_year, key=lambda f: f.filed) if same_period_prior_year else None
    return latest, prior


def compute_yoy_growth(current: float | None, prior: float | None) -> float | None:
    """Fraction, e.g. 0.12 for +12%. None if either figure is missing or
    the prior figure is zero (a growth rate off a zero base isn't a real
    number)."""
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior)


def build_financial_growth(revenue_facts: list[XbrlFact], eps_facts: list[XbrlFact]) -> FinancialGrowth:
    """Combines revenue and EPS into one result. The two can disagree (a
    company can grow revenue while losing money, or vice versa via
    buybacks) -- that's real and left visible in both fields rather than
    averaged away before you see it.
    """
    rev_latest, rev_prior = latest_and_prior_year(revenue_facts)
    eps_latest, eps_prior = latest_and_prior_year(eps_facts)

    period_source = rev_latest or eps_latest
    as_of_period = f"{period_source.fiscal_period} FY{period_source.fiscal_year}" if period_source else None

    return FinancialGrowth(
        revenue_yoy=compute_yoy_growth(
            rev_latest.value if rev_latest else None, rev_prior.value if rev_prior else None
        ),
        eps_yoy=compute_yoy_growth(
            eps_latest.value if eps_latest else None, eps_prior.value if eps_prior else None
        ),
        as_of_period=as_of_period,
    )
