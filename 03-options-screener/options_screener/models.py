from dataclasses import dataclass, field


@dataclass
class OptionContract:
    """One option contract, at a snapshot in time. `mid_price` is what
    every screen treats as "the premium" -- the last trade can be stale on
    a thin contract, but the bid/ask midpoint reflects where the market is
    right now.
    """

    ticker: str
    option_type: str  # "call" or "put"
    strike: float
    expiry: str  # ISO date, e.g. "2026-01-16"
    days_to_expiry: int
    bid: float
    ask: float
    last_price: float
    volume: int
    open_interest: int
    implied_volatility: float  # annualized, e.g. 0.35 for 35%

    @property
    def mid_price(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last_price


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float  # per 1 percentage point of IV
    fair_value: float


@dataclass
class MomentumResult:
    return_20d: float | None  # fraction, e.g. 0.08 for +8%
    rsi_14: float | None  # 0-100
    above_50sma: bool | None

    @property
    def bullish_score(self) -> float:
        """0-1. Each signal that fired bullish contributes a third -- an
        equal-weighted vote among the three, not one dominating metric."""
        parts = []
        if self.return_20d is not None:
            parts.append(1.0 if self.return_20d > 0 else 0.0)
        if self.rsi_14 is not None:
            parts.append(1.0 if self.rsi_14 > 55 else (0.0 if self.rsi_14 < 45 else 0.5))
        if self.above_50sma is not None:
            parts.append(1.0 if self.above_50sma else 0.0)
        return (sum(parts) / len(parts)) if parts else 0.5


@dataclass
class SentimentResult:
    score: float  # -1 (very negative) to +1 (very positive)
    headline_count: int
    positive_headlines: list[str] = field(default_factory=list)
    negative_headlines: list[str] = field(default_factory=list)

    @property
    def low_confidence(self) -> bool:
        return self.headline_count < 3


@dataclass
class VolumeSignal:
    contract: OptionContract
    volume_to_oi: float  # today's volume / open interest

    @property
    def is_unusual(self) -> bool:
        return self.volume_to_oi >= 1.0


@dataclass
class PopCandidate:
    """A ticker that screened well for the "bound to pop, far OTM" side,
    plus the actual contract(s) picked once it qualified."""

    ticker: str
    score: float  # 0-1 composite
    components: dict[str, float]
    momentum: MomentumResult
    sentiment: SentimentResult
    unusual_contracts: list[VolumeSignal]
    picked_contracts: list[tuple[OptionContract, Greeks]]
    notes: list[str]


@dataclass
class CheapCandidate:
    """A near-the-money, low-premium contract -- the other side of the
    screen, no signal scoring involved, just cheap and close to the
    money."""

    contract: OptionContract
    greeks: Greeks
    moneyness_pct: float  # (strike - spot) / spot, signed
