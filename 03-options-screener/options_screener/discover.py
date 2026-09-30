from .greeks import black_scholes_greeks, implied_strike_for_delta
from .models import MomentumResult, SentimentResult

# A broad, roughly market-average annualized volatility -- stands in for a
# stock's real IV in affordability_score, which is estimated *before* ever
# fetching a real option chain (that's the whole point of a cheap
# prefilter). A real stock's IV can be well above or below this; this is a
# prioritization signal for the prefilter, not a guarantee -- the expensive
# stage's own real, fetched IV is what actually decides a pick.
ASSUMED_IV_FOR_AFFORDABILITY = 0.35


def affordability_score(
    spot: float,
    cost_cap: float,
    delta_range: tuple[float, float],
    min_days_to_expiry: int,
    assumed_iv: float = ASSUMED_IV_FOR_AFFORDABILITY,
    risk_free_rate: float = 0.045,
) -> float:
    """0-1: how plausible it is that a real call in `delta_range` on this
    stock could cost `cost_cap` or less. Estimated from the spot price
    alone (already fetched for free during the prefilter, as the last
    close) plus an assumed IV, using the same Black-Scholes formula the
    rest of this tool trusts -- `implied_strike_for_delta` finds the
    strike for the delta band's midpoint, and `black_scholes_greeks` prices
    it. 1.0 means comfortably affordable (or cheaper); a fraction below
    1.0 scales down by roughly how many multiples of the cap the estimated
    contract would cost.

    This exists because momentum alone is blind to price: a real run's top
    15 by momentum were mostly $200-400+ stocks where no contract in a
    0.10-0.30 delta band could ever cost under a $30 cap, while cheaper
    stocks that could have produced a real pick never made the shortlist
    at all. Black-Scholes prices scale in a known way with the underlying
    price (holding strike/spot ratio, vol and time fixed), which is what
    makes spot price alone a meaningful, not arbitrary, signal here.
    """
    target_delta = sum(delta_range) / 2
    strike = implied_strike_for_delta(spot, target_delta, min_days_to_expiry, assumed_iv, "call", risk_free_rate)
    g = black_scholes_greeks(spot, strike, min_days_to_expiry, assumed_iv, "call", risk_free_rate)
    estimated_contract_cost = g.fair_value * 100
    if estimated_contract_cost <= 0:
        return 1.0
    return min(1.0, cost_cap / estimated_contract_cost)


def prefilter_score(
    momentum: MomentumResult, sentiment: SentimentResult | None = None, affordability: float | None = None
) -> float:
    """The cheap half of a two-stage scan -- momentum plus whichever of
    sentiment/affordability are supplied, no option chain and no news fetch
    involved, so this can run over hundreds of tickers before the
    expensive stage (fetching each one's option chain, and only then real
    multi-source news) narrows down to the handful actually worth it.
    Equal-weighted among whichever components are present, same
    explainability principle as screener.py's full composite score.

    `sentiment` is optional: a real 503-ticker run showed that fetching
    full news for every ticker just to rank them was the single biggest
    cost in the whole scan, and it couldn't have changed the ranking
    anyway -- a neutral sentiment score adds the exact same constant to
    every ticker. `cli.py`'s real prefilter loop doesn't fetch it at all.

    `affordability` (see affordability_score above) is the fix for a
    different real gap: momentum alone kept shortlisting expensive stocks
    whose options could never fit a real cost cap, while cheaper,
    genuinely-affordable stocks with decent momentum never got a look. It's
    optional for the same reason sentiment is -- existing callers (and
    tests) that only care about momentum shouldn't have to construct one.
    It's *appended* only when present rather than defaulted to a neutral
    value, unlike sentiment below -- there's no natural "neutral"
    affordability the way 0 is a neutral sentiment score, and every real
    caller that omits it (the tests that only care about momentum) should
    see a pure momentum-only score, not one silently split three ways.

    Missing sentiment defaults to a neutral 0.5 component rather than being
    omitted, so a ticker scored with no news fetched (the real prefilter
    loop) ranks identically to one scored with genuinely neutral news --
    both should read the same way to a caller.
    """
    sentiment_component = (sentiment.score + 1) / 2 if sentiment is not None else 0.5
    parts = [momentum.bullish_score, sentiment_component]
    if affordability is not None:
        parts.append(affordability)
    return sum(parts) / len(parts)


def shortlist(scored: list[tuple[str, float]], top_n: int = 15) -> list[str]:
    """Highest prefilter score first, ticker symbols only -- what decides
    which tickers are worth the expensive option-chain fetch."""
    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    return [ticker for ticker, _ in ranked[:top_n]]
