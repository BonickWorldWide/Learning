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


def large_move_frequency(closes: list[float], threshold: float = 0.05, window: int | None = None) -> float | None:
    """Fraction of trading days (over the trailing `window`, or all of
    `closes` if `window` is None) where the stock moved at least
    `threshold` in a single day, either direction -- a direct answer to
    "does this stock have a history of large leaps," and a genuinely
    different statistic from realized_volatility above, not a restatement
    of it. Realized volatility is built from the *variance* of daily
    returns, which a stock that drifts smoothly in a wide range and a
    stock that sits still for weeks then gaps 15% on an earnings surprise
    can both produce in similar amounts over a long enough window --
    variance doesn't distinguish steady wobble from discrete jumps. This
    counts the jumps directly. None when there are fewer than 2 closes to
    compute even one daily return from.
    """
    if window is not None:
        closes = closes[-(window + 1):]
    if len(closes) < 2:
        return None
    moves = [abs(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] > 0]
    if not moves:
        return None
    big_moves = sum(1 for m in moves if m >= threshold)
    return big_moves / len(moves)


def jump_score(frequency: float | None, ceiling: float) -> float | None:
    """0-1: how often this stock makes a large single-day move, scaled so
    `ceiling` (a frequency, e.g. 0.04 = roughly 10 times a year on a
    252-day history) reads as "genuinely jump-prone." 0.0 at a frequency
    of 0 (never a single big day in the window). None when `frequency` is
    None, so the composite score can omit it rather than guessing.
    """
    if frequency is None:
        return None
    if frequency <= 0:
        return 0.0
    if frequency >= ceiling:
        return 1.0
    return frequency / ceiling


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
