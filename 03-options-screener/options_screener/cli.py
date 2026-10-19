import argparse
import sys
import time
from datetime import date

from .backtest import evaluate_predictive_power, walk_history
from .config import load_config
from .discover import affordability_score, merge_universes, prefilter_score, shortlist
from .edgar_client import fetch_financial_facts, fetch_recent_8k_texts
from .financials import build_financial_growth
from .finnhub_client import fetch_finnhub_headlines
from .market_data import (
    fetch_cheap_volatile_universe,
    fetch_news_headlines,
    fetch_option_chain,
    fetch_price_history,
    fetch_seasonal_history,
    fetch_sp500_tickers,
)
from .momentum import build_momentum
from .models import CheapCandidate, PopCandidate
from .moneyness import find_cheap_near_money
from .screener import build_pop_candidate, rank_pop_candidates
from .seasonality import seasonal_bias
from .volatility import jump_score, large_move_frequency, movement_score, realized_volatility
from .volume_signal import average_volume
from .watchlist import load_watchlist

# Market-wide "don't fight the tape" ticker. SPY is fetched once per run
# (not once per ticker in that run), the same closes feed build_momentum
# the same way any other ticker's do, and the resulting bullish_score is
# passed into every ticker's prefilter_score/build_pop_candidate call
# identically -- see config.include_market_trend's docstring.
MARKET_TREND_TICKER = "SPY"

# Yahoo has no published rate-limit tier the way CollegeFootballData did,
# but hammering it with hundreds of sequential requests (discover's whole
# point) is exactly the kind of burst that got a real 429 out of CFBD.
# A real run confirmed this isn't hypothetical: roughly the back half of
# the S&P 500 failed news fetching identically, all starting midway
# through the same run -- the classic shape of a throttle kicking in after
# some request count, not scattered per-ticker bad luck. Bumped from 0.2s,
# and COOLDOWN_EVERY_N adds a longer breather periodically rather than
# just a bigger constant delay throughout -- neither is verified to clear
# the throttle, since it can't be tested against a live one from here.
#
# The prefilter loop below no longer fetches news at all (one plain GET
# per ticker instead of up to four sequential requests plus a now-removed
# 2s retry sleep -- see market_data.py), so this pacing is now protecting
# a much lighter loop than it was designed for. Left as-is rather than
# loosened, since there's no live evidence yet that a single GET per
# ticker at this volume is actually safe to run faster.
REQUEST_DELAY_SECONDS = 0.5
COOLDOWN_EVERY_N = 100
COOLDOWN_SECONDS = 15.0


def _fetch_market_trend(config) -> float | None:
    """SPY's own bullish_score, once per run -- None when
    `include_market_trend` is off or the fetch fails, in which case it's
    simply omitted from every ticker's score rather than guessed at."""
    if not config.include_market_trend:
        return None
    spy_closes, _ = fetch_price_history(MARKET_TREND_TICKER)
    if not spy_closes:
        return None
    return build_momentum(spy_closes).bullish_score


def _analyze_ticker(
    ticker: str, config, closes: list[float] | None = None, volumes: list[int] | None = None,
    headlines: list[str] | None = None, company_name: str | None = None, market_trend: float | None = None,
) -> tuple[list[CheapCandidate], PopCandidate]:
    """`closes`/`volumes`/`headlines` can be passed in already-fetched --
    `discover` computes all three during its cheap prefilter stage and
    would otherwise fetch them again here for the same ticker.
    `company_name` (from the S&P 500 table `discover` already has)
    sharpens the Google News fallback query; `screen`/`analyze` don't have
    one for an arbitrary watchlist ticker, so their fallback searches on
    the bare ticker instead."""
    calls, puts, spot = fetch_option_chain(ticker)
    if spot is None:
        raise ValueError(
            f"Couldn't get a current price for '{ticker}'. Check the message above this one -- "
            "it's either a bad ticker, or the network fetch itself failed (see README.md's "
            "'Getting real data in' section if you're running this somewhere with restricted network access)."
        )

    if closes is None:
        closes, volumes = fetch_price_history(ticker)
    if headlines is None:
        headlines = fetch_news_headlines(ticker, company_name=company_name)
    headlines = headlines + fetch_finnhub_headlines(ticker, config.finnhub_api_key)

    financial_growth = None
    if config.include_filings:
        headlines = headlines + fetch_recent_8k_texts(ticker, config.edgar_contact_email)
        revenue_facts, eps_facts = fetch_financial_facts(ticker, config.edgar_contact_email)
        financial_growth = build_financial_growth(revenue_facts, eps_facts)

    # A dedicated, longer (multi-year) fetch -- deliberately not
    # fetch_price_history's 1-year `closes`, which can hold at most one
    # occurrence of any given calendar month and so can never clear
    # seasonality.MIN_YEARS_FOR_SEASONAL_SIGNAL. Only reached here, at the
    # expensive per-ticker stage, never from discover's ~500-ticker
    # prefilter loop -- see config.include_seasonality's docstring.
    bias = None
    if config.include_seasonality:
        seasonal_dates, seasonal_closes = fetch_seasonal_history(ticker)
        if seasonal_dates:
            bias = seasonal_bias(seasonal_dates, seasonal_closes, date.today().month)

    cheap = find_cheap_near_money(
        calls + puts, spot, band_pct=config.near_money_band_pct, max_premium=config.cheap_max_premium,
        risk_free_rate=config.risk_free_rate, min_days_to_expiry=config.min_days_to_expiry,
    )
    pop = build_pop_candidate(
        ticker, calls, closes, headlines, spot,
        delta_range=config.pop_delta_range, max_premium=config.pop_max_premium,
        risk_free_rate=config.risk_free_rate, min_days_to_expiry=config.min_days_to_expiry,
        financial_growth=financial_growth, volumes=volumes,
        min_realized_volatility=config.min_realized_volatility,
        movement_score_ceiling=config.movement_score_ceiling,
        relative_volume_threshold=config.relative_volume_threshold,
        large_move_threshold=config.large_move_threshold,
        jump_frequency_ceiling=config.jump_frequency_ceiling,
        market_trend=market_trend,
        seasonal_bias=bias,
        seasonal_scale=config.seasonal_scale,
        iv_cheap_ceiling=config.iv_cheap_ceiling,
        iv_rich_floor=config.iv_rich_floor,
    )
    return cheap, pop


def _screen_tickers(
    tickers: list[str], config,
    precomputed: dict[str, tuple[list[float], list[int], list[str] | None]] | None = None,
    company_names: dict[str, str] | None = None,
    market_trend: float | None = None,
) -> tuple[dict[str, list[CheapCandidate]], list[PopCandidate]]:
    precomputed = precomputed or {}
    company_names = company_names or {}
    all_cheap: dict[str, list[CheapCandidate]] = {}
    all_pop: list[PopCandidate] = []

    for ticker in tickers:
        print(f"Fetching {ticker}...", file=sys.stderr)
        closes, volumes, headlines = precomputed.get(ticker, (None, None, None))
        try:
            cheap, pop = _analyze_ticker(
                ticker, config, closes=closes, volumes=volumes, headlines=headlines,
                company_name=company_names.get(ticker), market_trend=market_trend,
            )
        except ValueError as e:
            print(f"  (skipping {ticker}: {e})", file=sys.stderr)
            continue
        all_cheap[ticker] = cheap
        all_pop.append(pop)

    return all_cheap, all_pop


def _warn_if_filings_misconfigured(config) -> None:
    if config.include_filings and not config.edgar_contact_email:
        print(
            "  (include_filings is on but edgar_contact_email is blank in config.json -- SEC's fair-access "
            "policy requires every request to identify a real contact. Set edgar_contact_email before relying "
            "on this, otherwise a placeholder is being sent on your behalf.)",
            file=sys.stderr,
        )


def cmd_screen(args: argparse.Namespace) -> None:
    config = load_config()
    _warn_if_filings_misconfigured(config)
    tickers = load_watchlist()
    market_trend = _fetch_market_trend(config)
    all_cheap, all_pop = _screen_tickers(tickers, config, market_trend=market_trend)
    print_screen_report(all_cheap, all_pop, config)


def cmd_discover(args: argparse.Namespace) -> None:
    config = load_config()
    _warn_if_filings_misconfigured(config)
    universe, company_names = fetch_sp500_tickers()
    if not universe:
        raise ValueError("Couldn't fetch the S&P 500 ticker list -- check the network fetch message above.")

    # The S&P 500 is only ever mega/large-caps -- a real user pointed at RDW
    # (Redwire, ~$12.50/share with 15-cent calls) as exactly the kind of
    # cheap, volatile, decent-volume name this universe can never contain,
    # however good the scoring downstream gets. Yahoo's own screener finds
    # these server-side (one request, not one per candidate ticker) -- see
    # market_data.fetch_cheap_volatile_universe.
    if config.include_cheap_volatile_universe:
        cheap_tickers, cheap_names = fetch_cheap_volatile_universe(
            max_price=config.cheap_universe_max_price,
            min_avg_volume=config.cheap_universe_min_avg_volume,
            min_beta=config.cheap_universe_min_beta,
            count=config.cheap_universe_size,
        )
        if cheap_tickers:
            print(
                f"Added {len(cheap_tickers)} cheap/volatile ticker(s) from Yahoo's own screener (price < "
                f"${config.cheap_universe_max_price:.2f}, avg volume > {config.cheap_universe_min_avg_volume:,.0f}, "
                f"beta > {config.cheap_universe_min_beta}) -- names the S&P 500 list alone can never contain.",
                file=sys.stderr,
            )
        else:
            print("  (couldn't fetch the cheap/volatile screener universe -- see message above, if any)", file=sys.stderr)
        universe, company_names = merge_universes(universe, company_names, cheap_tickers, cheap_names)

    print(f"Prefiltering {len(universe)} tickers (momentum + affordability + movement -- no news fetch, no option chains yet)...", file=sys.stderr)
    market_trend = _fetch_market_trend(config)
    scored: list[tuple[str, float]] = []
    precomputed: dict[str, tuple[list[float], list[int], list[str] | None]] = {}
    skipped_too_calm = 0
    skipped_too_expensive = 0
    skipped_too_illiquid = 0
    for i, ticker in enumerate(universe):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        if i > 0 and i % COOLDOWN_EVERY_N == 0:
            print(f"  ...pausing {COOLDOWN_SECONDS:.0f}s after {i} tickers...", file=sys.stderr)
            time.sleep(COOLDOWN_SECONDS)
        closes, volumes = fetch_price_history(ticker)
        if not closes:
            continue
        # A hard skip, not `affordability_score`'s soft downweight -- direct
        # user ask: "remove any stocks that are over $250 to make it
        # quicker to process." The real speed win isn't the request that
        # just happened (the price has to be fetched to know it), it's
        # every one of these that no longer takes a `--top-n` slot at the
        # expensive stage, where a stock this priced would fetch a full
        # option chain and multi-source news only to confirm (again) what
        # affordability_score already knew -- no contract under any
        # realistic pop_max_contract_cost can exist on it. See "Real bugs
        # this surfaced" #9 for why that soft downweight alone wasn't
        # enough to stop it costing a shortlist slot.
        if closes[-1] > config.max_stock_price:
            skipped_too_expensive += 1
            continue
        # Another hard skip, same shape as the price cap above -- direct
        # user ask: "need a minimum of probably 5 to 10,000,000 volume on
        # the stock... to have enough volume in options." A different gap
        # than relative_volume_threshold (a ratio against the stock's OWN
        # baseline, which says nothing about whether that baseline is
        # itself enough volume to support a liquid options chain) -- see
        # volume_signal.average_volume.
        avg_vol = average_volume(volumes)
        if avg_vol is not None and avg_vol < config.min_stock_volume:
            skipped_too_illiquid += 1
            continue
        momentum = build_momentum(closes)
        # Estimated from spot price alone (the last close, already fetched
        # above for free) -- no option chain fetched here. This is the fix
        # for a real run where the momentum-only prefilter kept shortlisting
        # $200-400+ stocks (ADI, AMAT...) whose options could never fit the
        # configured cost cap, while cheaper stocks that could have produced
        # a real pick never made the shortlist at all. See
        # discover.affordability_score's docstring.
        affordability = affordability_score(
            spot=closes[-1], cost_cap=config.pop_max_contract_cost, delta_range=config.pop_delta_range,
            min_days_to_expiry=config.min_days_to_expiry,
        )
        # A hard skip, not just a lower score: a real run's shortlist kept
        # filling up with stocks that technically trended the right way but
        # realistically never move enough for a far-OTM call to land --
        # bouncing 0.5% for months, say. Dropping them here means they
        # never reach the expensive stage at all, not just rank lower than
        # something that would have outscored them anyway. See
        # screener.build_pop_candidate's matching hard floor and
        # volatility.py for the full reasoning.
        volatility = realized_volatility(closes)
        if volatility is not None and volatility < config.min_realized_volatility:
            skipped_too_calm += 1
            continue
        movement = movement_score(volatility, config.min_realized_volatility, config.movement_score_ceiling)
        # Cheap the same way `movement` is: both reuse the `closes` already
        # fetched above for momentum, so there's no reason to withhold the
        # history-of-large-leaps signal from the prefilter stage.
        jump_freq = large_move_frequency(closes, threshold=config.large_move_threshold)
        jump = jump_score(jump_freq, ceiling=config.jump_frequency_ceiling)
        # Headlines aren't fetched here at all -- a neutral sentiment adds
        # the same constant to every ticker's score (see prefilter_score's
        # docstring), so it can't change who makes the shortlist, and
        # fetching full multi-source news for all ~500 tickers just to
        # throw the ranking-irrelevant result away was the single biggest
        # cost in this loop. `None` (not a fetched list) tells
        # _analyze_ticker to fetch real headlines during the expensive
        # stage below, for only the tickers that actually made the cut.
        precomputed[ticker] = (closes, volumes, None)
        scored.append((
            ticker,
            prefilter_score(
                momentum, affordability=affordability, movement=movement, jump=jump, market_trend=market_trend,
            ),
        ))

    print(
        f"Skipped {skipped_too_expensive} ticker(s) priced over ${config.max_stock_price:.2f} -- no contract "
        "under any realistic cost cap can exist on them, and scanning them further would only cost a shortlist "
        "slot at the expensive stage for nothing.",
        file=sys.stderr,
    )
    print(
        f"Skipped {skipped_too_calm} ticker(s) whose realized volatility is below "
        f"{config.min_realized_volatility:.0%} annualized -- they don't move enough for a far-OTM call to be "
        "realistic, whatever their momentum looks like.",
        file=sys.stderr,
    )
    print(
        f"Skipped {skipped_too_illiquid} ticker(s) whose average daily volume is below "
        f"{config.min_stock_volume:,.0f} shares -- not enough real trading behind the stock to support a liquid "
        "options chain, whatever else looks bullish about it.",
        file=sys.stderr,
    )
    top_tickers = shortlist(scored, top_n=args.top_n)
    print(f"Shortlisted {len(top_tickers)} for full options analysis: {', '.join(top_tickers)}", file=sys.stderr)

    all_cheap, all_pop = _screen_tickers(
        top_tickers, config, precomputed=precomputed, company_names=company_names, market_trend=market_trend,
    )
    print_screen_report(all_cheap, all_pop, config)


def _print_capped(items: list[str], prefix: str, limit: int = 5) -> None:
    """A ticker with heavy coverage (a real AAPL run returned 257 headlines
    once Finnhub was added) would otherwise dump hundreds of lines to the
    console -- prints the first `limit` and says how many more there are,
    rather than flooding the terminal with something no one is going to
    read in full anyway."""
    for item in items[:limit]:
        print(f"{prefix}{item}")
    if len(items) > limit:
        print(f"  ...and {len(items) - limit} more")


def _rationale(cand: PopCandidate) -> str:
    """A one-line, plain-English reading of why a ticker scored the way it
    did -- which components actually carried it, the actual number behind
    every component (not just the ones strong/weak enough to call out by
    name), and any reason to discount the score (too few headlines to
    trust the sentiment number).

    A real run showed moderate components (sentiment around 0.5-0.7, say)
    silently dropped out of this line entirely, since they're neither
    "strong" nor "weak" -- which reads as "nothing but unusual volume
    mattered" even when sentiment was a real, substantial third of the
    score. The numeric breakdown at the end is what actually answers "is
    X being used" without having to cross-reference the components table
    printed further down the report.
    """
    strong = [name.replace("_", " ") for name, val in cand.components.items() if val >= 0.75]
    weak = [name.replace("_", " ") for name, val in cand.components.items() if val <= 0.25]
    bits = []
    if strong:
        bits.append("strong " + ", ".join(strong))
    if weak:
        bits.append("weak " + ", ".join(weak))
    if not bits:
        bits.append("moderate across the board")
    breakdown = ", ".join(f"{name.replace('_', ' ')} {val:.2f}" for name, val in cand.components.items())
    bits.append(f"({breakdown})")
    if cand.sentiment.low_confidence:
        bits.append("sentiment unconfirmed -- too few headlines to trust")
    return "; ".join(bits)


def _top_picks(ranked: list[PopCandidate], limit: int = 5):
    """Every (candidate, contract, greeks) that actually cleared both bars
    -- a high enough score AND a real contract in the configured delta/cost
    range -- flattened across tickers and sorted best-score-first, cheapest
    as the tiebreak. A candidate that scored well but picked nothing
    (see screener.build_pop_candidate's docstring) simply contributes
    nothing here rather than showing up as an empty entry.
    """
    flat = [(cand, contract, greeks) for cand in ranked for contract, greeks in cand.picked_contracts]
    # Highest score first, then highest delta as the tiebreak -- not
    # cheapest. A real run's headline pick for a ticker was consistently
    # its deepest, cheapest, least-likely-to-land contract (see
    # screener.build_pop_candidate's matching comment), because sorting by
    # price alone has nothing to do with which contract is actually the
    # better "bound to pop" bet among ones that already cleared the cost
    # cap.
    flat.sort(key=lambda triple: (-triple[0].score, -triple[2].delta))
    return flat[:limit]


def print_screen_report(all_cheap: dict, all_pop: list[PopCandidate], config) -> None:
    ranked = rank_pop_candidates(all_pop, min_score=config.pop_min_score)
    top_picks = _top_picks(ranked)

    print("=" * 70)
    print("TOP PICKS -- highest-scoring tickers with an actual qualifying contract")
    print("=" * 70)
    if not top_picks:
        print("  Nothing both scored well enough and had a contract in the configured delta/cost range this run.")
        print("  See ALL BOUND-TO-POP CANDIDATES below -- a ticker can score well with nothing to buy today.")
    for rank, (cand, contract, greeks) in enumerate(top_picks, start=1):
        print(f"\n  #{rank}  {cand.ticker}  {contract.option_type} ${contract.strike:.2f}  exp {contract.expiry} ({contract.days_to_expiry}d)")
        print(f"      Cost: ${contract.mid_price:.2f}/share = ${contract.total_cost:.0f} for one contract (100 shares)")
        print(f"      Delta {greeks.delta:.4f}   IV {contract.implied_volatility:.1%}   Score {cand.score:.2f}")
        print(f"      Why: {_rationale(cand)}")

    print("\n" + "=" * 70)
    print("CHEAP, NEAR-THE-MONEY CONTRACTS -- no signal scoring, just close to the money and low-cost")
    print("=" * 70)
    any_cheap = False
    for ticker, candidates in all_cheap.items():
        for cand in candidates[:5]:
            any_cheap = True
            c = cand.contract
            print(
                f"  {ticker:6s} {c.option_type:4s} ${c.strike:<8.2f} exp {c.expiry} ({c.days_to_expiry}d)  "
                f"${c.mid_price:.2f}/share (${c.total_cost:.0f}/contract)  delta {cand.greeks.delta:+.4f}  "
                f"iv {c.implied_volatility:.1%}  ({cand.moneyness_pct:+.1%} from spot)"
            )
    if not any_cheap:
        print("  None found within the configured band/cost limit.")

    print("\n" + "=" * 70)
    print("WHY EACH TICKER DID OR DIDN'T MAKE TOP PICKS -- not a buy list, see TOP PICKS above for that")
    print("=" * 70)
    if not ranked:
        print("  Nothing cleared the score bar this run.")
    for cand in ranked:
        print(f"\n  {cand.ticker}  score {cand.score:.2f}  ({_rationale(cand)})")
        for name, value in cand.components.items():
            print(f"    {name}: {value:.2f}")
        for contract, greeks in cand.picked_contracts:
            print(
                f"    -> {contract.option_type} ${contract.strike:.2f} exp {contract.expiry} ({contract.days_to_expiry}d)  "
                f"${contract.mid_price:.2f}/share (${contract.total_cost:.0f}/contract)  "
                f"delta {greeks.delta:.4f}  iv {contract.implied_volatility:.1%}"
            )
        for note in cand.notes:
            print(f"    ! {note}")


def cmd_analyze(args: argparse.Namespace) -> None:
    config = load_config()
    _warn_if_filings_misconfigured(config)
    market_trend = _fetch_market_trend(config)
    cheap, pop = _analyze_ticker(args.ticker, config, market_trend=market_trend)

    print("=" * 70)
    print(f"{args.ticker} -- CHEAP, NEAR-THE-MONEY CONTRACTS")
    print("=" * 70)
    if not cheap:
        print("  None found within the configured band/cost limit.")
    for cand in cheap:
        c = cand.contract
        print(
            f"  {c.option_type:4s} ${c.strike:<8.2f} exp {c.expiry} ({c.days_to_expiry}d)  "
            f"${c.mid_price:.2f}/share (${c.total_cost:.0f}/contract)  "
            f"delta {cand.greeks.delta:+.4f}  theta {cand.greeks.theta:+.3f}  iv {c.implied_volatility:.1%}  "
            f"({cand.moneyness_pct:+.1%} from spot)"
        )

    print("\n" + "=" * 70)
    print(f"{args.ticker} -- BOUND-TO-POP SIGNAL BREAKDOWN")
    print("=" * 70)
    print(f"\nComposite score: {pop.score:.2f}   ({_rationale(pop)})")
    for name, value in pop.components.items():
        print(f"  {name}: {value:.2f}")
    print(f"\nMomentum: return_20d={pop.momentum.return_20d}, rsi_14={pop.momentum.rsi_14}, "
          f"above_50sma={pop.momentum.above_50sma}")
    if pop.realized_volatility is not None:
        print(f"Realized volatility: {pop.realized_volatility:.1%} annualized")
    if pop.relative_volume is not None:
        print(f"Relative volume: {pop.relative_volume:.1f}x its own recent baseline")
    if pop.large_move_frequency is not None:
        print(f"History of large leaps: {pop.large_move_frequency:.1%} of trading days moved "
              f"{config.large_move_threshold:.0%} or more in a single day")
    if pop.market_trend is not None:
        print(f"Broad market trend (SPY): {pop.market_trend:.2f} bullish_score -- applied identically to every "
              "ticker this run")
    if pop.seasonal_bias is not None:
        print(f"Seasonal bias for this month, historically: {pop.seasonal_bias:+.1%} average return")
    if pop.iv_realized_ratio is not None:
        print(f"Options pricing vs. reality: implied vol is {pop.iv_realized_ratio:.2f}x realized volatility "
              f"({'cheap' if pop.iv_realized_ratio <= config.iv_cheap_ceiling else 'rich' if pop.iv_realized_ratio >= config.iv_rich_floor else 'fair'})")
    print(f"Sentiment: {pop.sentiment.score:+.2f} over {pop.sentiment.headline_count} headline(s)")
    _print_capped(pop.sentiment.positive_headlines, prefix="  + ")
    _print_capped(pop.sentiment.negative_headlines, prefix="  - ")
    if pop.financial_growth is not None:
        fg = pop.financial_growth
        rev = f"{fg.revenue_yoy:+.1%}" if fg.revenue_yoy is not None else "n/a"
        eps = f"{fg.eps_yoy:+.1%}" if fg.eps_yoy is not None else "n/a"
        print(f"Financials ({fg.as_of_period or 'no data'}): revenue YoY {rev}, EPS YoY {eps}")
    if pop.unusual_contracts:
        print("\nUnusual call volume:")
        for signal in pop.unusual_contracts:
            c = signal.contract
            print(f"  ${c.strike:.2f} exp {c.expiry}: volume {c.volume} vs OI {c.open_interest} ({signal.volume_to_oi:.1f}x)")
    if pop.picked_contracts:
        print("\nQualifying far-OTM calls (in the configured delta band, under the cost cap):")
        for contract, greeks in pop.picked_contracts:
            print(
                f"  ${contract.strike:.2f} exp {contract.expiry} ({contract.days_to_expiry}d)  "
                f"${contract.mid_price:.2f}/share (${contract.total_cost:.0f}/contract)  "
                f"delta {greeks.delta:.4f}  iv {contract.implied_volatility:.1%}"
            )
    for note in pop.notes:
        print(f"! {note}")


# One row of walk_history's output per signal this reports on -- "composite"
# is the only one that's never None (it always has at least momentum to
# average), so it's the only one with no missing-data caveat to print.
BACKTEST_SIGNALS = ["momentum", "movement", "jump", "market_trend", "seasonal", "composite"]


def cmd_backtest(args: argparse.Namespace) -> None:
    """Does any of this actually predict anything? Walks each ticker's own
    price history day by day (never looking ahead -- see
    backtest.walk_history's docstring), computing the same price-only
    signals the live tool uses, then checks whether a day that scored high
    was actually followed by the kind of move a far-OTM call needs. This
    is the one thing missing before any of these signals should be
    trusted: every one of them computes a plausible-sounding number, and
    none of them had ever been checked against what actually happened.
    """
    config = load_config()
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else load_watchlist()
    if not tickers:
        raise ValueError("No tickers to backtest -- pass --tickers AAPL,MSFT,... or add some to watchlist.json.")
    score_threshold = args.score_threshold if args.score_threshold is not None else config.pop_min_score

    print(f"Fetching {args.years} year(s) of SPY history for market trend...", file=sys.stderr)
    _, spy_closes = fetch_seasonal_history("SPY", years=args.years)
    if not spy_closes:
        print("  (couldn't fetch SPY history -- market_trend will be skipped for every ticker)", file=sys.stderr)

    pooled: dict[str, list[tuple[float, float]]] = {name: [] for name in BACKTEST_SIGNALS}
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        print(f"Backtesting {ticker}...", file=sys.stderr)
        dates, closes = fetch_seasonal_history(ticker, years=args.years)
        if not closes:
            print(f"  (skipping {ticker}: couldn't fetch history)", file=sys.stderr)
            continue
        rows = walk_history(
            closes, dates, horizon=args.horizon, spy_closes=spy_closes or None,
            min_realized_volatility=config.min_realized_volatility,
            movement_score_ceiling=config.movement_score_ceiling,
            large_move_threshold=config.large_move_threshold,
            jump_frequency_ceiling=config.jump_frequency_ceiling,
            seasonal_scale=config.seasonal_scale,
        )
        for row in rows:
            for name in BACKTEST_SIGNALS:
                value = row[name]
                if value is not None:
                    pooled[name].append((value, row["forward_return"]))

    print("\n" + "=" * 70)
    print(
        f"BACKTEST -- {len(tickers)} ticker(s), {args.years} year(s) of history, {args.horizon}-trading-day "
        f"horizon, success = a {args.success_threshold:+.0%} move, score threshold {score_threshold:.2f}"
    )
    print("=" * 70)
    print(
        "This is a hit-rate comparison, not a statistical significance test -- an edge on a small sample can\n"
        "easily be noise. More tickers, more years of history, and more days clearing the score threshold all\n"
        "make a number here more trustworthy, not a bigger edge by itself."
    )
    for name in BACKTEST_SIGNALS:
        result = evaluate_predictive_power(
            pooled[name], score_threshold=score_threshold, success_threshold=args.success_threshold
        )
        print(f"\n{name}:")
        print(f"  {result.n_total} usable day(s) across every ticker, {result.n_signal} cleared the score threshold")
        if result.baseline_hit_rate is None:
            print("  (no data -- this signal never had enough history to compute on any ticker here)")
            continue
        print(f"  Baseline hit rate (any day, regardless of score): {result.baseline_hit_rate:.1%}")
        if result.signal_hit_rate is None:
            print(f"  (no day cleared the {score_threshold:.2f} score threshold -- can't measure a signal hit rate)")
            continue
        print(f"  Signal hit rate (score >= {score_threshold:.2f}): {result.signal_hit_rate:.1%}")
        print(f"  Edge: {result.edge:+.1%}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="options-screener", description="Screens options for cheap near-the-money contracts and far-OTM 'bound to pop' candidates."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    screen_parser = subparsers.add_parser("screen", help="Scan your whole watchlist")
    screen_parser.set_defaults(func=cmd_screen)

    discover_parser = subparsers.add_parser(
        "discover", help="Scan the S&P 500 instead of a watchlist -- prefilters cheaply, then screens the top candidates"
    )
    discover_parser.add_argument(
        "--top-n", type=int, default=15,
        help="How many tickers move from the cheap prefilter to full options analysis (default 15)",
    )
    discover_parser.set_defaults(func=cmd_discover)

    analyze_parser = subparsers.add_parser("analyze", help="Full breakdown for one ticker")
    analyze_parser.add_argument("ticker", help='e.g. "AAPL"')
    analyze_parser.set_defaults(func=cmd_analyze)

    backtest_parser = subparsers.add_parser(
        "backtest", help="Check whether the price-only signals actually predicted anything, historically"
    )
    backtest_parser.add_argument(
        "--tickers", default=None,
        help="Comma-separated tickers to backtest (default: your watchlist)",
    )
    backtest_parser.add_argument(
        "--horizon", type=int, default=20,
        help="Trading days ahead to check for a move (default 20, ~1 month)",
    )
    backtest_parser.add_argument(
        "--success-threshold", type=float, default=0.10,
        help="How big a forward move counts as a hit, as a fraction (default 0.10 = 10%%)",
    )
    backtest_parser.add_argument(
        "--score-threshold", type=float, default=None,
        help="Score a day must clear to count as 'this signal said yes' (default: config.json's pop_min_score)",
    )
    backtest_parser.add_argument(
        "--years", type=int, default=5,
        help="Years of history to fetch per ticker (default 5)",
    )
    backtest_parser.set_defaults(func=cmd_backtest)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
