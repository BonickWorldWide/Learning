def iv_realized_ratio(implied_volatility: float, realized_volatility: float | None) -> float | None:
    """How rich this option's priced-in volatility is relative to the
    stock's own actual realized volatility -- 1.0 means the option is
    priced exactly in line with how much the stock has really been moving;
    above 1.0 means it's pricing in MORE movement than has actually
    happened (expensive insurance); below 1.0 means it's pricing in LESS
    (cheap relative to the stock's real recent behavior).

    This is the honest, practical substitute for a true IV rank/percentile
    (today's IV compared against its own trailing-year range), which needs
    a time series of the option's own historical implied volatility --
    data no free source provides. `yfinance`'s option chain only ever
    returns CURRENT IV, never history, and there's no bundled or free
    alternative. Comparing today's IV against the stock's own
    `realized_volatility` (already computed from free price history
    this tool already fetches) needs no new data at all, and answers a
    closely related, still-useful question: is this option cheap or
    expensive relative to how the stock actually trades right now, even
    though it can't say whether that's cheap or expensive relative to this
    *option's own* history.

    None when `realized_volatility` is None or not positive (can't form a
    meaningful ratio against zero or unknown volatility).
    """
    if realized_volatility is None or realized_volatility <= 0:
        return None
    return implied_volatility / realized_volatility


def iv_value_score(ratio: float | None, cheap_ceiling: float, rich_floor: float) -> float | None:
    """0-1: 1.0 at or below `cheap_ceiling` (cheap -- full score), 0.0 at
    or above `rich_floor` (rich -- the option is pricing in a lot more
    movement than the stock has actually delivered), linear in between.

    Inverted compared to movement_score/jump_score, where a HIGHER raw
    number is better: here a LOWER ratio is better, because this tool is
    about buying optionality, and overpaying for the same directional bet
    is a worse trade even on a stock that goes on to move exactly as
    hoped. Direction-agnostic the same way movement/jump_risk are -- this
    says whether the bet is well-priced, not whether it's the right bet.

    None when `ratio` is None.
    """
    if ratio is None:
        return None
    if ratio <= cheap_ceiling:
        return 1.0
    if ratio >= rich_floor:
        return 0.0
    return (rich_floor - ratio) / (rich_floor - cheap_ceiling)
