from dataclasses import dataclass
from datetime import date

from .momentum import build_momentum
from .seasonality import seasonal_bias, seasonal_score
from .volatility import jump_score, large_move_frequency, movement_score, realized_volatility

# Trading days of history required before walk_history starts scoring a
# day at all -- enough for build_momentum's 50-day SMA (the longest of its
# three signals) to be real rather than None, so every row this produces
# reflects the full, three-part momentum signal the live tool actually
# uses, not a thin early-history version of it.
MIN_HISTORY_FOR_SCORE = 60


def forward_return(closes: list[float], index: int, horizon: int) -> float | None:
    """The simple return from `closes[index]` to `closes[index + horizon]`
    -- what actually happened `horizon` trading days after a score was
    computed at `index`. None when there isn't `horizon` more days of
    history yet to know the outcome, or `closes[index]` isn't positive.
    """
    target = index + horizon
    if target >= len(closes) or closes[index] <= 0:
        return None
    return (closes[target] - closes[index]) / closes[index]


def historical_composite_score(
    momentum: float,
    movement: float | None = None,
    jump: float | None = None,
    market_trend: float | None = None,
    seasonal: float | None = None,
) -> float:
    """Equal-weighted average of whichever price-only signals are
    available, the same "None means omit" rule as discover.prefilter_score
    and screener.build_pop_candidate -- but built for backtesting
    specifically: it leaves out sentiment and affordability (no historical
    headlines exist to replay, and affordability is about cost, not
    direction), and it includes `seasonal`, which the live prefilter
    deliberately omits for per-ticker fetch-cost reasons that don't apply
    here -- walking history already in memory costs nothing extra per
    point.
    """
    parts = [momentum]
    if movement is not None:
        parts.append(movement)
    if jump is not None:
        parts.append(jump)
    if market_trend is not None:
        parts.append(market_trend)
    if seasonal is not None:
        parts.append(seasonal)
    return sum(parts) / len(parts)


def walk_history(
    closes: list[float],
    dates: list[date],
    horizon: int,
    spy_closes: list[float] | None = None,
    min_realized_volatility: float = 0.35,
    movement_score_ceiling: float = 0.80,
    large_move_threshold: float = 0.05,
    jump_frequency_ceiling: float = 0.04,
    seasonal_scale: float = 0.05,
) -> list[dict]:
    """Walks one stock's price history day by day, computing each signal
    with ONLY the data that would have actually been available on that day
    -- `closes[:i+1]`, never a later close -- and pairing it with what
    really happened `horizon` trading days afterward (`forward_return`).

    This no-lookahead rule is the one thing that makes a backtest honest.
    A score computed with the benefit of the whole history (not just the
    slice up to that day) would look predictive no matter what signal it
    was built from -- that's the single most common way a backtest lies
    to the person running it, and it's silent: the code still runs and
    still produces a number.

    Returns one dict per usable day: `momentum`, `movement`, `jump`,
    `market_trend`, `seasonal`, `composite`, `forward_return`. Each signal
    key is None exactly when the live pipeline would also have scored it
    None at that point (not enough trailing history yet) -- this measures
    the signals as they actually run in `discover`/`screen`, not an
    idealized version of them with every signal always present.
    """
    rows = []
    for i in range(MIN_HISTORY_FOR_SCORE, len(closes)):
        ret = forward_return(closes, i, horizon)
        if ret is None:
            break  # every later day has even less forward history -- nothing more to find

        closes_so_far = closes[: i + 1]
        momentum = build_momentum(closes_so_far).bullish_score

        volatility = realized_volatility(closes_so_far)
        movement = movement_score(volatility, min_realized_volatility, movement_score_ceiling)

        jump_freq = large_move_frequency(closes_so_far, threshold=large_move_threshold)
        jump = jump_score(jump_freq, ceiling=jump_frequency_ceiling)

        market_trend = None
        if spy_closes is not None and i < len(spy_closes):
            market_trend = build_momentum(spy_closes[: i + 1]).bullish_score

        bias = seasonal_bias(dates[: i + 1], closes_so_far, dates[i].month)
        seasonal = seasonal_score(bias, seasonal_scale)

        composite = historical_composite_score(momentum, movement, jump, market_trend, seasonal)

        rows.append({
            "momentum": momentum,
            "movement": movement,
            "jump": jump,
            "market_trend": market_trend,
            "seasonal": seasonal,
            "composite": composite,
            "forward_return": ret,
        })
    return rows


@dataclass
class BacktestResult:
    """Does a score actually predict the outcome it claims to? `edge` is
    the one number that answers it: the hit rate among days where the
    score cleared `score_threshold`, minus the baseline hit rate across
    every day regardless of score -- P(success | high score) vs
    P(success). A signal with an edge near zero is indistinguishable from
    noise here, however sensible its reasoning sounded when it was
    written. None fields mean there wasn't enough data to compute that
    figure at all, not that the edge was zero -- a real, different answer.
    """

    n_total: int
    n_signal: int
    baseline_hit_rate: float | None
    signal_hit_rate: float | None

    @property
    def edge(self) -> float | None:
        if self.baseline_hit_rate is None or self.signal_hit_rate is None:
            return None
        return self.signal_hit_rate - self.baseline_hit_rate


def evaluate_predictive_power(
    scores_and_returns: list[tuple[float, float]], score_threshold: float, success_threshold: float
) -> BacktestResult:
    """`scores_and_returns` is (score, forward_return) pairs -- typically
    one signal's column from one or more `walk_history` runs, pooled
    across tickers. `success_threshold` is how big a forward move counts
    as "the bet paid off" (e.g. 0.10 for a 10% move over the horizon);
    `score_threshold` is how high the score had to be to count as "this
    signal said yes."
    """
    n_total = len(scores_and_returns)
    if n_total == 0:
        return BacktestResult(n_total=0, n_signal=0, baseline_hit_rate=None, signal_hit_rate=None)

    baseline_hits = sum(1 for _, ret in scores_and_returns if ret >= success_threshold)
    baseline_hit_rate = baseline_hits / n_total

    signal_returns = [ret for score, ret in scores_and_returns if score >= score_threshold]
    n_signal = len(signal_returns)
    if n_signal == 0:
        return BacktestResult(n_total=n_total, n_signal=0, baseline_hit_rate=baseline_hit_rate, signal_hit_rate=None)

    signal_hits = sum(1 for ret in signal_returns if ret >= success_threshold)
    signal_hit_rate = signal_hits / n_signal
    return BacktestResult(
        n_total=n_total, n_signal=n_signal, baseline_hit_rate=baseline_hit_rate, signal_hit_rate=signal_hit_rate
    )
