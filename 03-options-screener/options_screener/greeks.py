import math
from statistics import NormalDist

from .models import Greeks

SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def black_scholes_greeks(
    spot: float,
    strike: float,
    days_to_expiry: int,
    implied_volatility: float,
    option_type: str,
    risk_free_rate: float = 0.045,
) -> Greeks:
    """Delta, gamma, theta, vega and fair value from Black-Scholes -- no
    dividend yield, which is the standard simplification for a short-dated
    equity option and the one every screener like this makes; it would
    matter for a long-dated option on a high-dividend stock, which isn't
    what a "cheap near-the-money" or "far OTM lottery ticket" screen is
    looking at anyway.

    On expiry day (days_to_expiry <= 0) there's no time value left to model
    -- delta collapses to whether the option is in the money, and every
    other Greek is zero.
    """
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    if days_to_expiry <= 0 or implied_volatility <= 0:
        in_the_money = strike < spot if option_type == "call" else strike > spot
        intrinsic = max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
        delta = (1.0 if option_type == "call" else -1.0) if in_the_money else 0.0
        return Greeks(delta=delta, gamma=0.0, theta=0.0, vega=0.0, fair_value=intrinsic)

    t = days_to_expiry / 365.0
    sigma = implied_volatility
    sqrt_t = math.sqrt(t)

    d1 = (math.log(spot / strike) + (risk_free_rate + sigma**2 / 2) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    discounted_strike = strike * math.exp(-risk_free_rate * t)
    gamma = _norm_pdf(d1) / (spot * sigma * sqrt_t)
    vega = spot * _norm_pdf(d1) * sqrt_t / 100  # per 1 percentage point of IV

    if option_type == "call":
        delta = _norm_cdf(d1)
        fair_value = spot * _norm_cdf(d1) - discounted_strike * _norm_cdf(d2)
        theta_per_year = (
            -(spot * _norm_pdf(d1) * sigma) / (2 * sqrt_t) - risk_free_rate * discounted_strike * _norm_cdf(d2)
        )
    else:
        delta = _norm_cdf(d1) - 1
        fair_value = discounted_strike * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        theta_per_year = (
            -(spot * _norm_pdf(d1) * sigma) / (2 * sqrt_t) + risk_free_rate * discounted_strike * _norm_cdf(-d2)
        )

    return Greeks(delta=delta, gamma=gamma, theta=theta_per_year / 365, vega=vega, fair_value=fair_value)


def implied_strike_for_delta(
    spot: float,
    target_delta: float,
    days_to_expiry: int,
    implied_volatility: float,
    option_type: str = "call",
    risk_free_rate: float = 0.045,
) -> float:
    """The strike that would produce `target_delta`, for an assumed
    spot/IV/dte -- Black-Scholes delta inverted in closed form (via the
    inverse normal CDF), not a numerical search. Lets a caller ask "what
    would a 0.20-delta contract cost on this stock" *before* ever fetching
    a real option chain, given some assumed IV -- see
    discover.affordability_score, which is the actual reason this exists:
    a real run's momentum-only prefilter kept shortlisting $200-400+
    stocks where no contract in the target delta band could ever be cheap
    enough for the configured cost cap, while cheaper stocks that could
    have produced a real pick never got considered at all.
    """
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    t = days_to_expiry / 365.0
    n_d1 = target_delta if option_type == "call" else target_delta + 1
    d1 = NormalDist().inv_cdf(n_d1)
    sigma = implied_volatility
    return spot * math.exp((risk_free_rate + sigma**2 / 2) * t - d1 * sigma * math.sqrt(t))
