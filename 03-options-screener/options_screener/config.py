import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class Config:
    """`cheap_max_contract_cost` and `pop_max_contract_cost` are what buying
    ONE contract actually costs, in dollars -- $30 means $30, not $0.30. A
    real user read a quoted per-share price ("$1.65") as the total cost
    when it actually meant $165 (options always trade 100 shares at a
    time), so these fields are named and stored in the unit a person
    actually thinks in. `cheap_max_premium`/`pop_max_premium` (below) do
    the /100 conversion into the per-share price the pure screening
    functions compare against -- nothing downstream of config.py needs to
    know contract sizes exist.
    """

    near_money_band_pct: float
    cheap_max_contract_cost: float
    pop_delta_min: float
    pop_delta_max: float
    pop_max_contract_cost: float
    pop_min_score: float
    risk_free_rate: float
    min_days_to_expiry: int
    edgar_contact_email: str
    include_filings: bool
    finnhub_api_key: str
    # Annualized realized volatility a stock must clear before the "pop"
    # screen will ever surface a contract to buy on it -- a hard floor, not
    # just a score penalty. A real run kept picking far-OTM calls on names
    # that realistically never move enough to reach that strike; see
    # screener.build_pop_candidate and volatility.py. 0.35 (35%) is a
    # reasoned starting point (quiet mega-caps often run 15-25%
    # annualized, genuinely volatile small/mid-caps 45-90%+), not a value
    # swept against real outcomes -- same "every number is a knob, tune it
    # against what you see" spirit as every other constant in this file.
    min_realized_volatility: float
    # Where the movement score (the *ranking* signal among stocks that
    # clear the floor above) saturates at 1.0. Also a reasoned anchor, not
    # a backtested one.
    movement_score_ceiling: float
    # A stock's own recent trading volume must be at least this many times
    # its own baseline before stock_volume counts it as elevated -- see
    # volume_signal.relative_volume. 1.5x is a common "notably active"
    # heuristic, not a precisely derived number.
    relative_volume_threshold: float
    # A single-day move at least this big counts as a "jump" for
    # volatility.large_move_frequency -- a direct history-of-large-leaps
    # signal, distinct from realized_volatility (which measures day-to-day
    # wobble, not discrete gaps). 0.05 (5%) is a reasoned definition of
    # "notable" for an individual stock, not a derived threshold.
    large_move_threshold: float
    # Where the jump-frequency *ranking* signal saturates at 1.0 -- 0.04
    # means a stock clearing the threshold above on ~4% of trading days
    # (roughly 10 times a year on a 252-day history) reads as fully
    # jump-prone.
    jump_frequency_ceiling: float
    # Blends the broader market's own momentum (SPY) into every ticker's
    # score, identically for all of them in one run -- "don't fight the
    # tape." Doesn't change ranking *among* tickers in a run (every ticker
    # gets the same number), but does raise or lower every score together
    # depending on whether the broad market itself is trending up or down.
    include_market_trend: bool
    # Turns on the seasonality signal (seasonality.py) -- real, but a
    # heavier per-ticker fetch (several years of history instead of one),
    # so it's opt-in and only ever runs for the handful of tickers that
    # reach the expensive stage, never the full prefilter universe.
    include_seasonality: bool
    # A historical average monthly return of +/- this much (5%) maps to
    # the full +/-1.0 end of the seasonal score -- see
    # seasonality.seasonal_score. A reasoned scale, not a derived one.
    seasonal_scale: float

    @property
    def pop_delta_range(self) -> tuple[float, float]:
        return (self.pop_delta_min, self.pop_delta_max)

    @property
    def cheap_max_premium(self) -> float:
        """Per-share quoted price -- what moneyness.find_cheap_near_money
        actually compares a contract's mid_price against."""
        return self.cheap_max_contract_cost / 100

    @property
    def pop_max_premium(self) -> float:
        return self.pop_max_contract_cost / 100


def load_config(config_file: Path = DEFAULT_CONFIG_FILE) -> Config:
    data = {}
    if config_file.exists():
        data = json.loads(config_file.read_text())

    return Config(
        near_money_band_pct=float(data.get("near_money_band_pct", 0.05)),
        cheap_max_contract_cost=float(data.get("cheap_max_contract_cost", 200.00)),
        pop_delta_min=float(data.get("pop_delta_min", 0.10)),
        pop_delta_max=float(data.get("pop_delta_max", 0.30)),
        pop_max_contract_cost=float(data.get("pop_max_contract_cost", 100.00)),
        pop_min_score=float(data.get("pop_min_score", 0.6)),
        risk_free_rate=float(data.get("risk_free_rate", 0.045)),
        min_days_to_expiry=int(data.get("min_days_to_expiry", 7)),
        edgar_contact_email=str(data.get("edgar_contact_email", "")),
        include_filings=bool(data.get("include_filings", False)),
        finnhub_api_key=str(data.get("finnhub_api_key", "")),
        min_realized_volatility=float(data.get("min_realized_volatility", 0.35)),
        movement_score_ceiling=float(data.get("movement_score_ceiling", 0.80)),
        relative_volume_threshold=float(data.get("relative_volume_threshold", 1.5)),
        large_move_threshold=float(data.get("large_move_threshold", 0.05)),
        jump_frequency_ceiling=float(data.get("jump_frequency_ceiling", 0.04)),
        include_market_trend=bool(data.get("include_market_trend", True)),
        include_seasonality=bool(data.get("include_seasonality", True)),
        seasonal_scale=float(data.get("seasonal_scale", 0.05)),
    )
