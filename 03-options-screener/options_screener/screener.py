from .greeks import black_scholes_greeks
from .momentum import build_momentum
from .models import FinancialGrowth, OptionContract, PopCandidate
from .seasonality import seasonal_score
from .sentiment import score_headlines
from .volatility import jump_score, large_move_frequency, movement_score, realized_volatility
from .volume_signal import relative_volume, unusual_volume_contracts


def build_pop_candidate(
    ticker: str,
    call_contracts: list[OptionContract],
    closes: list[float],
    headlines: list[str],
    spot: float,
    delta_range: tuple[float, float] = (0.10, 0.30),
    max_premium: float = 1.00,
    top_n: int = 3,
    risk_free_rate: float = 0.045,
    min_days_to_expiry: int = 7,
    financial_growth: FinancialGrowth | None = None,
    volumes: list[int] | None = None,
    min_realized_volatility: float = 0.35,
    movement_score_ceiling: float = 0.80,
    relative_volume_threshold: float = 1.5,
    large_move_threshold: float = 0.05,
    jump_frequency_ceiling: float = 0.04,
    market_trend: float | None = None,
    seasonal_bias: float | None = None,
    seasonal_scale: float = 0.05,
) -> PopCandidate:
    """One ticker's "bound to pop, far OTM" screen: a composite score from
    momentum + news sentiment + unusual call-volume + how much this stock
    actually moves and trades (+ real filed revenue/EPS growth, if
    `financial_growth` is supplied), plus the actual cheap, low-delta call
    contracts that qualify once a ticker looks good.

    The score is an equal-weighted average of whichever components are
    present -- `financial_growth` is optional (SEC EDGAR fetching is opt-in,
    see cli.py/config.py) and simply isn't counted when it's None, rather
    than forcing a fourth vote that always reads neutral. Explainable over
    accurate-but-opaque, the same choice project 02's power rating made.

    `min_realized_volatility` is a **hard floor**, not just another vote:
    a real run kept surfacing far-OTM calls on stocks that historically
    barely move at all -- every other signal here (momentum, sentiment,
    unusual option volume) is directional or event-driven, and none of
    them ask whether the stock's *typical* move is even large enough to
    plausibly reach a far-OTM strike. A stock below the floor never gets a
    picked contract, however good its other signals look -- see
    volatility.py for the full reasoning. `movement_score_ceiling` sets
    where the *ranking* signal among stocks that do clear the floor
    saturates. `relative_volume_threshold` is the bar for `volumes` (daily
    trading volume, oldest first, same length as `closes`) to count the
    stock as trading unusually actively right now -- a different, broader
    signal than `unusual_volume_contracts` below, which only looks at one
    option contract's volume against its own open interest.

    The score and the contract pick are independent on purpose -- a ticker
    can score well with nothing in `picked_contracts` (nothing cheap enough
    or in the delta band right now, or too calm to pick anything at all),
    which is a real, useful answer ("this name looks bullish, but there's
    no cheap lottery ticket for it today"), not a bug to hide.

    `min_days_to_expiry` drops contracts closer to expiry than that,
    applied before both the unusual-volume check and the delta-band pick.
    A real run came back with zero picks across 15 different tickers --
    every one of the nearest expiries was 2-3 days out, and at that range
    delta collapses toward 0 or 1 within a percent or two of the strike, so
    the 0.10-0.30 band was a sliver of strikes that either didn't exist or
    cost more than the premium cap. The same near-expiry contracts also
    make a noisy, false "unusual volume" reading, since volume churns
    heavily right before a contract expires regardless of any real signal.

    Three more optional signals answer "give me better picks for highly
    probable stocks to move, with better volume" more directly than
    volatility/relative-volume alone: `large_move_threshold` and
    `jump_frequency_ceiling` compute a "how often does this stock actually
    gap" ranking signal from the same `closes` already fetched (see
    volatility.large_move_frequency/jump_score -- a genuinely different
    statistic from realized volatility, since a jump-prone-but-otherwise-
    calm stock is exactly what a far-OTM call wants). `market_trend` is
    precomputed once per *run* (not per ticker) from the broader market's
    own momentum (SPY) and passed in here identically for every ticker --
    "don't fight the tape": it never changes ranking among tickers in one
    run, only raises or lowers every score together. `seasonal_bias` is
    precomputed per ticker from a separate multi-year history fetch (see
    seasonality.py); `seasonal_scale` converts it to a 0-1 score here, same
    as everywhere else that takes a raw signal and a scale/ceiling.
    """
    eligible = [c for c in call_contracts if c.days_to_expiry >= min_days_to_expiry]

    momentum = build_momentum(closes)
    sentiment = score_headlines(headlines)
    unusual = unusual_volume_contracts(eligible)
    volatility = realized_volatility(closes)
    movement = movement_score(volatility, min_realized_volatility, movement_score_ceiling)
    rel_vol = relative_volume(volumes) if volumes else None
    jump_freq = large_move_frequency(closes, threshold=large_move_threshold)
    jump = jump_score(jump_freq, ceiling=jump_frequency_ceiling)
    seasonal = seasonal_score(seasonal_bias, scale=seasonal_scale)

    components = {
        "momentum": momentum.bullish_score,
        "sentiment": (sentiment.score + 1) / 2,  # rescale -1..+1 to 0..1
        "unusual_volume": 1.0 if unusual else 0.0,
    }
    if movement is not None:
        components["movement"] = movement
    if rel_vol is not None:
        components["stock_volume"] = 1.0 if rel_vol >= relative_volume_threshold else 0.0
    if financial_growth is not None:
        components["financial_growth"] = financial_growth.bullish_score
    if jump is not None:
        components["jump_risk"] = jump
    if market_trend is not None:
        components["market_trend"] = market_trend
    if seasonal is not None:
        components["seasonal"] = seasonal
    score = sum(components.values()) / len(components)

    # A stock whose realized volatility can't clear the floor never gets a
    # pick -- checked once, up front, so it overrides everything below
    # rather than needing to be threaded through every branch.
    too_calm = volatility is not None and volatility < min_realized_volatility

    in_delta_band = []
    picked = []
    for c in eligible:
        g = black_scholes_greeks(spot, c.strike, c.days_to_expiry, c.implied_volatility, "call", risk_free_rate)
        if delta_range[0] <= g.delta <= delta_range[1]:
            in_delta_band.append((c, g))
            if not too_calm and 0 < c.mid_price <= max_premium:
                picked.append((c, g))
    # Highest delta first, not cheapest first. A real run surfaced mostly
    # ~0.10-delta picks -- the very bottom of the band, i.e. the deepest,
    # least-likely-to-actually-pop contracts -- simply because they were
    # the cheapest ones that happened to qualify. Every contract here has
    # already cleared the cost cap, so among the ones the player can
    # afford, the one closer to actually landing in the money is the
    # better "bound to pop" pick, not the one that happens to cost a few
    # dollars less.
    picked.sort(key=lambda pair: (-pair[1].delta, pair[0].mid_price))
    picked = picked[:top_n]

    notes = []
    if sentiment.low_confidence:
        notes.append(f"Only {sentiment.headline_count} headline(s) found -- sentiment is low-confidence.")
    if not unusual:
        notes.append("No unusual call volume detected.")
    if too_calm:
        notes.append(
            f"Realized volatility is only {volatility:.0%} annualized (need at least "
            f"{min_realized_volatility:.0%}) -- this stock historically doesn't move enough for a far-OTM call "
            "to be a realistic bet, whatever else looks bullish about it. No contract is picked here regardless "
            "of the delta band or cost cap."
        )
    elif not picked:
        if in_delta_band:
            # There IS a contract in the delta band -- it's specifically
            # the cost cap ruling it out, and the cheapest one found tells
            # you exactly how high to raise it. A real run showed this is
            # usually the actual constraint, not a lack of contracts: a
            # 0.10-0.30 delta call on a $400 stock can cost $200+ per
            # contract, which no reasonable "cheap lottery ticket" cap
            # would ever clear -- that's the stock being too expensive for
            # this budget, not a bug.
            cheapest = min(in_delta_band, key=lambda pair: pair[0].mid_price)
            notes.append(
                f"{len(in_delta_band)} call(s) are in the delta band [{delta_range[0]:.2f}, {delta_range[1]:.2f}], "
                f"but the cheapest costs ${cheapest[0].mid_price:.2f}/share "
                f"(${cheapest[0].mid_price * 100:.0f}/contract) -- over your "
                f"${max_premium:.2f}/share (${max_premium * 100:.0f}/contract) cap. Raise "
                f"pop_max_contract_cost to at least ${cheapest[0].mid_price * 100:.0f} to see a pick on this ticker."
            )
        else:
            notes.append(
                f"None of {len(eligible)} eligible contract(s) has delta in "
                f"[{delta_range[0]:.2f}, {delta_range[1]:.2f}] at all, regardless of price."
            )

    if financial_growth is not None and financial_growth.as_of_period is None:
        notes.append("No SEC financial data found for this ticker -- financial_growth contributed a neutral vote.")

    return PopCandidate(
        ticker=ticker,
        score=score,
        components=components,
        momentum=momentum,
        sentiment=sentiment,
        unusual_contracts=unusual,
        picked_contracts=picked,
        notes=notes,
        financial_growth=financial_growth,
        realized_volatility=volatility,
        relative_volume=rel_vol,
        large_move_frequency=jump_freq,
        market_trend=market_trend,
        seasonal_bias=seasonal_bias,
    )


def rank_pop_candidates(candidates: list[PopCandidate], min_score: float = 0.6) -> list[PopCandidate]:
    """Highest score first, dropping anything under the bar -- a candidate
    with no picked contract can still rank (see build_pop_candidate's
    docstring), so this filters on the composite score alone, not on
    whether a contract came back.
    """
    return sorted((c for c in candidates if c.score >= min_score), key=lambda c: c.score, reverse=True)
