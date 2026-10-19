import math

# Trading days in a year -- the standard annualization factor for a daily
# realized-volatility calculation.
ANNUALIZATION_FACTOR = math.sqrt(252)

# How many trailing trading days the realized-volatility calc looks at.
REALIZED_VOL_WINDOW = 20


def realized_volatility(closes: list[float], window: int = REALIZED_VOL_WINDOW) -> float | None:
    """Annualized realized volatility over the trailing `window` trading
    days, from daily log returns -- how much this stock actually swings,
    independent of direction. None when there isn't at least `window`+1
    closes to compute a return series from.

    This exists because every other signal in this screener
    (momentum.build_momentum) is purely directional: a stock that crawled
    up 0.3% over a month scores exactly as "bullish" as one that ripped
    15%, because return_20d > 0, RSI and above/below the 50-day average
    all only ask *which way*, never *how much*. A far-OTM call on a stock
    with ~10% annualized volatility is a bet on a move that essentially
    never happens for that name, however bullish its direction looks --
    this is the signal that can actually say so. See
    screener.build_pop_candidate for how it's used: both as a hard floor
    (a stock below it is excluded from the pickable contracts outright,
    not just scored lower) and as a continuous ranking signal among the
    stocks that clear it (volatility.movement_score).
    """
    if len(closes) <= window:
        return None
    recent = closes[-(window + 1):]
    returns = [math.log(recent[i] / recent[i - 1]) for i in range(1, len(recent)) if recent[i - 1] > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * ANNUALIZATION_FACTOR


def movement_score(volatility: float | None, floor: float, ceiling: float) -> float | None:
    """0-1: how strong a ranking signal this stock's realized volatility is,
    *among stocks that already clear the hard floor* -- 0.0 right at
    `floor` (barely qualifies), 1.0 at `ceiling` or above (a genuinely
    volatile mover), linear in between. None when `volatility` is None
    (not enough price history), so the composite score can omit it rather
    than guessing.

    Deliberately shares `floor` with the hard exclusion in
    build_pop_candidate rather than having its own separate cutoff -- one
    number means "barely qualifies" and "scores near zero on movement"
    always agree with each other, instead of two thresholds that could
    disagree about the same stock.
    """
    if volatility is None:
        return None
    if volatility <= floor:
        return 0.0
    if volatility >= ceiling:
        return 1.0
    return (volatility - floor) / (ceiling - floor)
