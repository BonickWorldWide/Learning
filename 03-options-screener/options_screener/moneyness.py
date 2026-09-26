from .greeks import black_scholes_greeks
from .models import CheapCandidate, OptionContract


def moneyness_pct(contract: OptionContract, spot: float) -> float:
    """Signed distance from the money, as a fraction of spot. Positive
    means the strike is above spot (OTM for a call, ITM for a put)."""
    return (contract.strike - spot) / spot


def find_cheap_near_money(
    contracts: list[OptionContract],
    spot: float,
    band_pct: float = 0.05,
    max_premium: float = 2.00,
    risk_free_rate: float = 0.045,
) -> list[CheapCandidate]:
    """Contracts within `band_pct` of the current price (either side, calls
    and puts both) priced at or under `max_premium` -- cheap, high-leverage
    bets close to breakeven rather than a directional signal pick. Sorted
    cheapest first.
    """
    candidates = []
    for c in contracts:
        pct = moneyness_pct(c, spot)
        if abs(pct) > band_pct:
            continue
        premium = c.mid_price
        if premium <= 0 or premium > max_premium:
            continue
        greeks = black_scholes_greeks(spot, c.strike, c.days_to_expiry, c.implied_volatility, c.option_type, risk_free_rate)
        candidates.append(CheapCandidate(contract=c, greeks=greeks, moneyness_pct=pct))

    return sorted(candidates, key=lambda cand: cand.contract.mid_price)
