from collections import defaultdict
from datetime import date

# A month's historical return is only trusted once at least this many
# distinct years of it are on record -- a "pattern" from 1-2 occurrences
# is indistinguishable from noise, and reporting one anyway would be
# presenting a coincidence as a signal.
MIN_YEARS_FOR_SEASONAL_SIGNAL = 3


def monthly_returns_by_year(dates: list[date], closes: list[float]) -> dict[tuple[int, int], float]:
    """{(year, month): that month's real return} -- the first and last
    close actually present in each calendar month, not an approximation.
    A month with fewer than 2 closes (the stock's history starts or ends
    mid-month) is skipped rather than guessed at.
    """
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for d, c in zip(dates, closes):
        buckets[(d.year, d.month)].append(c)
    return {
        key: (values[-1] - values[0]) / values[0]
        for key, values in buckets.items()
        if len(values) >= 2 and values[0] > 0
    }


def seasonal_bias(
    dates: list[date], closes: list[float], target_month: int, min_years: int = MIN_YEARS_FOR_SEASONAL_SIGNAL
) -> float | None:
    """Average historical return during `target_month`, across however
    many distinct years of it are in `dates`/`closes` -- "has this stock
    historically done well or poorly this time of year." None when fewer
    than `min_years` occurrences of that month are available.

    This is the fix for a different real gap than realized volatility or
    jump frequency: those both ask "how much does this stock move," never
    "is there a time of year it tends to move a particular direction" --
    some names have real, repeatable seasonal patterns (retailers around
    the holidays, energy names around winter demand) that a
    purely-reactive momentum/volatility read has no way to see coming.
    """
    monthly = monthly_returns_by_year(dates, closes)
    same_month = [ret for (_, month), ret in monthly.items() if month == target_month]
    if len(same_month) < min_years:
        return None
    return sum(same_month) / len(same_month)


def seasonal_score(bias: float | None, scale: float) -> float | None:
    """0-1, centered at 0.5: a historical average monthly return of
    `+scale` or more maps to 1.0, `-scale` or less to 0.0, linear and
    clamped in between -- unlike movement_score/jump_score, which measure
    a magnitude (always >= 0), a seasonal bias is directional, so this is
    centered on "no historical pattern either way" rather than anchored
    at zero. None when `bias` is None (not enough years of history for
    this month to trust).
    """
    if bias is None:
        return None
    return min(1.0, max(0.0, 0.5 + bias / (2 * scale)))
