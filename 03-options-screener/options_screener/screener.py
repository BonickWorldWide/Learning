from .greeks import black_scholes_greeks
from .momentum import build_momentum
from .models import FinancialGrowth, OptionContract, PopCandidate
from .sentiment import score_headlines
from .volume_signal import unusual_volume_contracts


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
) -> PopCandidate:
    """One ticker's "bound to pop, far OTM" screen: a composite score from
    momentum + news sentiment + unusual call-volume (+ real filed
    revenue/EPS growth, if `financial_growth` is supplied), plus the actual
    cheap, low-delta call contracts that qualify once a ticker looks good.

    The score is an equal-weighted average of whichever components are
    present -- `financial_growth` is optional (SEC EDGAR fetching is opt-in,
    see cli.py/config.py) and simply isn't counted when it's None, rather
    than forcing a fourth vote that always reads neutral. Explainable over
    accurate-but-opaque, the same choice project 02's power rating made.

    The score and the contract pick are independent on purpose -- a ticker
    can score well with nothing in `picked_contracts` (nothing cheap enough
    or in the delta band right now), which is a real, useful answer
    ("this name looks bullish, but there's no cheap lottery ticket for it
    today"), not a bug to hide.

    `min_days_to_expiry` drops contracts closer to expiry than that,
    applied before both the unusual-volume check and the delta-band pick.
    A real run came back with zero picks across 15 different tickers --
    every one of the nearest expiries was 2-3 days out, and at that range
    delta collapses toward 0 or 1 within a percent or two of the strike, so
    the 0.10-0.30 band was a sliver of strikes that either didn't exist or
    cost more than the premium cap. The same near-expiry contracts also
    make a noisy, false "unusual volume" reading, since volume churns
    heavily right before a contract expires regardless of any real signal.
    """
    eligible = [c for c in call_contracts if c.days_to_expiry >= min_days_to_expiry]

    momentum = build_momentum(closes)
    sentiment = score_headlines(headlines)
    unusual = unusual_volume_contracts(eligible)

    components = {
        "momentum": momentum.bullish_score,
        "sentiment": (sentiment.score + 1) / 2,  # rescale -1..+1 to 0..1
        "unusual_volume": 1.0 if unusual else 0.0,
    }
    if financial_growth is not None:
        components["financial_growth"] = financial_growth.bullish_score
    score = sum(components.values()) / len(components)

    in_delta_band = []
    picked = []
    for c in eligible:
        g = black_scholes_greeks(spot, c.strike, c.days_to_expiry, c.implied_volatility, "call", risk_free_rate)
        if delta_range[0] <= g.delta <= delta_range[1]:
            in_delta_band.append((c, g))
            if 0 < c.mid_price <= max_premium:
                picked.append((c, g))
    picked.sort(key=lambda pair: pair[0].mid_price)
    picked = picked[:top_n]

    notes = []
    if sentiment.low_confidence:
        notes.append(f"Only {sentiment.headline_count} headline(s) found -- sentiment is low-confidence.")
    if not unusual:
        notes.append("No unusual call volume detected.")
    if not picked:
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
    )


def rank_pop_candidates(candidates: list[PopCandidate], min_score: float = 0.6) -> list[PopCandidate]:
    """Highest score first, dropping anything under the bar -- a candidate
    with no picked contract can still rank (see build_pop_candidate's
    docstring), so this filters on the composite score alone, not on
    whether a contract came back.
    """
    return sorted((c for c in candidates if c.score >= min_score), key=lambda c: c.score, reverse=True)
