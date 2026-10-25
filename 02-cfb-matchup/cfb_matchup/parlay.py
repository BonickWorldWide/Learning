from dataclasses import dataclass

from .simulate import moneyline_to_implied_prob

# A real user's pattern: "$5 parlay, 5 to 6 of the picks need to hit in 1
# bet." Checked against their own actual slips (all-or-nothing, same games
# as the straight-bet analysis elsewhere in this README): every one of 4
# recent 5-6 leg parlays busted, including one that hit 4 of its 5 legs --
# a near-miss on a straight bet is a complete loss on a parlay, because
# there's no partial credit. That's the gap this module closes: a straight
# bet's own expected value (moneyline_ev in simulate.py) says nothing
# about whether a SPECIFIC COMBINATION of legs, bet together as one
# all-or-nothing ticket, is itself worth taking.
DEFAULT_PARLAY_STAKE = 5.0


def american_to_decimal(odds: int) -> float:
    """Decimal odds -- what to multiply a stake by to get the total return
    (stake included) if this one leg wins. The natural unit for combining
    multiple legs: a parlay's combined payout is the PRODUCT of each leg's
    own decimal odds, the same way combined_probability below multiplies
    probabilities.
    """
    if odds < 0:
        return 1 + 100 / (-odds)
    return 1 + odds / 100


def combined_decimal_odds(odds_list: list[int]) -> float:
    result = 1.0
    for odds in odds_list:
        result *= american_to_decimal(odds)
    return result


def combined_probability(probs: list[float]) -> float:
    """The combined chance every leg in an all-or-nothing parlay hits --
    the product of each leg's own win/cover probability, assuming each
    game's outcome is independent of the others (true for different games
    on different fields; would NOT hold for multiple props inside the same
    game, which this isn't built for).

    This is the number a parlay bettor actually needs and a straight
    bettor doesn't: five legs each individually a coin flip combine to a
    ~3% chance of cashing (0.5^5), not 50%. Going 4 of 5 on a parlay this
    size is not "close" -- it's the same complete loss as going 0 of 5.
    """
    result = 1.0
    for p in probs:
        result *= p
    return result


def parlay_payout(odds_list: list[int], stake: float = DEFAULT_PARLAY_STAKE) -> float:
    """Total return (stake included) if every leg hits."""
    return stake * combined_decimal_odds(odds_list)


def parlay_ev(probs: list[float], odds_list: list[int], stake: float = DEFAULT_PARLAY_STAKE) -> float:
    """Expected profit, in dollars, from this exact combination of legs as
    one all-or-nothing ticket -- given that `probs` are the TRUE
    probability of each leg (the model's own number for that bet, not the
    market's). The parlay version of simulate.moneyline_ev, same
    reasoning: agreeing with the market on who covers/wins says nothing
    about whether the combined price is worth paying, and for a parlay
    that question compounds across every leg at once rather than applying
    to just one bet.
    """
    combined_prob = combined_probability(probs)
    payout = parlay_payout(odds_list, stake)
    profit_if_win = payout - stake
    return combined_prob * profit_if_win - (1 - combined_prob) * stake


@dataclass
class LegEdge:
    """One leg's own edge over what its price demands -- `model_prob` -
    `market_implied_prob`. Zero or negative means this leg is priced at
    least as confidently as the model itself is, so including it adds pure
    bust risk to the parlay without any offsetting value: dropping any
    leg with `edge <= 0` always raises the parlay's own expected value,
    never lowers it, because nothing compensates for the extra
    all-or-nothing uncertainty a fairly-priced leg adds for free.
    """

    index: int
    model_prob: float
    market_implied_prob: float

    @property
    def edge(self) -> float:
        return self.model_prob - self.market_implied_prob


def leg_edges(probs: list[float], odds_list: list[int]) -> list[LegEdge]:
    """One LegEdge per leg, worst edge first -- so the legs most worth
    dropping from the ticket (or betting straight instead, away from the
    all-or-nothing structure) surface at the top rather than requiring a
    manual scan of every leg's numbers.
    """
    edges = [
        LegEdge(index=i, model_prob=prob, market_implied_prob=moneyline_to_implied_prob(odds))
        for i, (prob, odds) in enumerate(zip(probs, odds_list))
    ]
    return sorted(edges, key=lambda e: e.edge)
