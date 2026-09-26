from .greeks import black_scholes_greeks
from .momentum import build_momentum
from .models import OptionContract, PopCandidate
from .sentiment import score_headlines
from .volume_signal import unusual_volume_contracts

# Equal-weighted, and each one visible in `components` -- explainable over
# accurate-but-opaque, the same choice project 02's power rating made.
POP_SCORE_WEIGHTS = {"momentum": 1 / 3, "sentiment": 1 / 3, "unusual_volume": 1 / 3}


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
) -> PopCandidate:
    """One ticker's "bound to pop, far OTM" screen: a composite score from
    momentum + news sentiment + unusual call-volume, plus the actual cheap,
    low-delta call contracts that qualify once a ticker looks good.

    The score and the contract pick are independent on purpose -- a ticker
    can score well with nothing in `picked_contracts` (nothing cheap enough
    or in the delta band right now), which is a real, useful answer
    ("this name looks bullish, but there's no cheap lottery ticket for it
    today"), not a bug to hide.
    """
    momentum = build_momentum(closes)
    sentiment = score_headlines(headlines)
    unusual = unusual_volume_contracts(call_contracts)

    components = {
        "momentum": momentum.bullish_score,
        "sentiment": (sentiment.score + 1) / 2,  # rescale -1..+1 to 0..1
        "unusual_volume": 1.0 if unusual else 0.0,
    }
    score = sum(components[k] * POP_SCORE_WEIGHTS[k] for k in POP_SCORE_WEIGHTS)

    picked = []
    for c in call_contracts:
        g = black_scholes_greeks(spot, c.strike, c.days_to_expiry, c.implied_volatility, "call", risk_free_rate)
        if delta_range[0] <= g.delta <= delta_range[1] and 0 < c.mid_price <= max_premium:
            picked.append((c, g))
    picked.sort(key=lambda pair: pair[0].mid_price)
    picked = picked[:top_n]

    notes = []
    if sentiment.low_confidence:
        notes.append(f"Only {sentiment.headline_count} headline(s) found -- sentiment is low-confidence.")
    if not unusual:
        notes.append("No unusual call volume detected.")
    if not picked:
        notes.append(
            f"No call found with delta in [{delta_range[0]:.2f}, {delta_range[1]:.2f}] "
            f"and premium <= ${max_premium:.2f}."
        )

    return PopCandidate(
        ticker=ticker,
        score=score,
        components=components,
        momentum=momentum,
        sentiment=sentiment,
        unusual_contracts=unusual,
        picked_contracts=picked,
        notes=notes,
    )


def rank_pop_candidates(candidates: list[PopCandidate], min_score: float = 0.6) -> list[PopCandidate]:
    """Highest score first, dropping anything under the bar -- a candidate
    with no picked contract can still rank (see build_pop_candidate's
    docstring), so this filters on the composite score alone, not on
    whether a contract came back.
    """
    return sorted((c for c in candidates if c.score >= min_score), key=lambda c: c.score, reverse=True)
