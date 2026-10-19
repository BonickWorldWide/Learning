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
    # Merges Yahoo's own screener universe (cheap, liquid, volatile names
    # -- see market_data.fetch_cheap_volatile_universe) into `discover`'s
    # S&P 500 list. A real user pointed at RDW (Redwire, ~$12.50 with
    # 15-cent calls) as a name the S&P 500-only universe can never contain
    # regardless of how good the scoring is -- this is a fix for the
    # universe itself, not another signal.
    include_cheap_volatile_universe: bool
    # Upper bound on share price for the screener universe above -- "cheap"
    # the way the user meant it (RDW at $12.50), not a backtested cutoff.
    cheap_universe_max_price: float
    # Floor on 3-month average daily volume for the screener universe --
    # "pretty good volume," a reasoned liquidity bar, not a derived one.
    # Direct user ask for an absolute floor, not relative_volume_threshold's
    # ratio-to-own-baseline: "need a minimum of probably 5 to 10,000,000
    # volume on the stock... to have enough volume in options." 5,000,000
    # is the lower end of that stated range -- a reasoned starting point,
    # raisable toward 10,000,000 for a stricter bar.
    cheap_universe_min_avg_volume: float
    # Floor on beta (volatility relative to the market) for the screener
    # universe -- a cheap, per-request proxy for "genuinely volatile" that
    # avoids fetching real price history for hundreds of candidates just to
    # build the universe in the first place. The cheap prefilter stage
    # downstream still floors on the stock's own real realized_volatility
    # once that history is actually fetched.
    cheap_universe_min_beta: float
    # How many tickers to request from the screener in one call -- Yahoo
    # caps this at 250.
    cheap_universe_size: int
    # A hard exclusion in discover's prefilter, not affordability_score's
    # soft downweight -- direct user ask: "remove any stocks that are over
    # $250 to make it quicker to process." A stock this priced can't
    # produce a contract under any realistic pop_max_contract_cost (see
    # "Real bugs this surfaced" #9), so letting it take a --top-n slot at
    # the expensive stage only spends a full option-chain + multi-source
    # news fetch to confirm, again, what affordability_score already knew.
    max_stock_price: float
    # The same absolute floor as cheap_universe_min_avg_volume above, but
    # for discover's main S&P 500 prefilter loop -- see
    # volume_signal.average_volume. The S&P 500 is almost entirely liquid
    # mega/large-caps, so this will rarely trigger there, but it closes the
    # same real gap: `relative_volume_threshold`'s ratio says a stock is
    # trading more than *its own* usual pace, which says nothing about
    # whether that pace is itself enough to support a liquid options chain.
    min_stock_volume: float

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
        include_cheap_volatile_universe=bool(data.get("include_cheap_volatile_universe", True)),
        cheap_universe_max_price=float(data.get("cheap_universe_max_price", 20.00)),
        cheap_universe_min_avg_volume=float(data.get("cheap_universe_min_avg_volume", 5_000_000)),
        cheap_universe_min_beta=float(data.get("cheap_universe_min_beta", 1.3)),
        cheap_universe_size=int(data.get("cheap_universe_size", 250)),
        max_stock_price=float(data.get("max_stock_price", 250.00)),
        min_stock_volume=float(data.get("min_stock_volume", 5_000_000)),
    )
