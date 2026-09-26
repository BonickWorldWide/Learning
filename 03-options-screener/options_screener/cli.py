import argparse
import sys

from .config import load_config
from .market_data import fetch_news_headlines, fetch_option_chain, fetch_price_history
from .models import CheapCandidate, PopCandidate
from .moneyness import find_cheap_near_money
from .screener import build_pop_candidate, rank_pop_candidates
from .watchlist import load_watchlist


def _analyze_ticker(ticker: str, config) -> tuple[list[CheapCandidate], PopCandidate]:
    calls, puts, spot = fetch_option_chain(ticker)
    if spot is None:
        raise ValueError(
            f"Couldn't get a current price for '{ticker}'. Check the message above this one -- "
            "it's either a bad ticker, or the network fetch itself failed (see README.md's "
            "'Getting real data in' section if you're running this somewhere with restricted network access)."
        )

    closes = fetch_price_history(ticker)
    headlines = fetch_news_headlines(ticker)

    cheap = find_cheap_near_money(
        calls + puts, spot, band_pct=config.near_money_band_pct, max_premium=config.cheap_max_premium,
        risk_free_rate=config.risk_free_rate,
    )
    pop = build_pop_candidate(
        ticker, calls, closes, headlines, spot,
        delta_range=config.pop_delta_range, max_premium=config.pop_max_premium,
        risk_free_rate=config.risk_free_rate,
    )
    return cheap, pop


def cmd_screen(args: argparse.Namespace) -> None:
    config = load_config()
    tickers = load_watchlist()

    all_cheap: dict[str, list[CheapCandidate]] = {}
    all_pop: list[PopCandidate] = []

    for ticker in tickers:
        print(f"Fetching {ticker}...", file=sys.stderr)
        try:
            cheap, pop = _analyze_ticker(ticker, config)
        except ValueError as e:
            print(f"  (skipping {ticker}: {e})", file=sys.stderr)
            continue
        all_cheap[ticker] = cheap
        all_pop.append(pop)

    print_screen_report(all_cheap, all_pop, config)


def print_screen_report(all_cheap: dict, all_pop: list[PopCandidate], config) -> None:
    print("=" * 70)
    print("CHEAP, NEAR-THE-MONEY CONTRACTS")
    print("=" * 70)
    any_cheap = False
    for ticker, candidates in all_cheap.items():
        for cand in candidates[:5]:
            any_cheap = True
            c = cand.contract
            print(
                f"  {ticker:6s} {c.option_type:4s} ${c.strike:<8.2f} exp {c.expiry}  "
                f"${c.mid_price:.2f}  delta {cand.greeks.delta:+.2f}  "
                f"({cand.moneyness_pct:+.1%} from spot)"
            )
    if not any_cheap:
        print("  None found within the configured band/premium.")

    print("\n" + "=" * 70)
    print("BOUND-TO-POP CANDIDATES (far OTM calls, ranked by signal score)")
    print("=" * 70)
    ranked = rank_pop_candidates(all_pop, min_score=config.pop_min_score)
    if not ranked:
        print("  Nothing cleared the score bar this run.")
    for cand in ranked:
        print(f"\n  {cand.ticker}  score {cand.score:.2f}")
        for name, value in cand.components.items():
            print(f"    {name}: {value:.2f}")
        for contract, greeks in cand.picked_contracts:
            print(
                f"    -> {contract.option_type} ${contract.strike:.2f} exp {contract.expiry}  "
                f"${contract.mid_price:.2f}  delta {greeks.delta:.2f}"
            )
        for note in cand.notes:
            print(f"    ! {note}")


def cmd_analyze(args: argparse.Namespace) -> None:
    config = load_config()
    cheap, pop = _analyze_ticker(args.ticker, config)

    print("=" * 70)
    print(f"{args.ticker} -- CHEAP, NEAR-THE-MONEY CONTRACTS")
    print("=" * 70)
    if not cheap:
        print("  None found within the configured band/premium.")
    for cand in cheap:
        c = cand.contract
        print(
            f"  {c.option_type:4s} ${c.strike:<8.2f} exp {c.expiry}  ${c.mid_price:.2f}  "
            f"delta {cand.greeks.delta:+.2f}  theta {cand.greeks.theta:+.3f}  "
            f"({cand.moneyness_pct:+.1%} from spot)"
        )

    print("\n" + "=" * 70)
    print(f"{args.ticker} -- BOUND-TO-POP SIGNAL BREAKDOWN")
    print("=" * 70)
    print(f"\nComposite score: {pop.score:.2f}")
    for name, value in pop.components.items():
        print(f"  {name}: {value:.2f}")
    print(f"\nMomentum: return_20d={pop.momentum.return_20d}, rsi_14={pop.momentum.rsi_14}, "
          f"above_50sma={pop.momentum.above_50sma}")
    print(f"Sentiment: {pop.sentiment.score:+.2f} over {pop.sentiment.headline_count} headline(s)")
    for h in pop.sentiment.positive_headlines:
        print(f"  + {h}")
    for h in pop.sentiment.negative_headlines:
        print(f"  - {h}")
    if pop.unusual_contracts:
        print("\nUnusual call volume:")
        for signal in pop.unusual_contracts:
            c = signal.contract
            print(f"  ${c.strike:.2f} exp {c.expiry}: volume {c.volume} vs OI {c.open_interest} ({signal.volume_to_oi:.1f}x)")
    if pop.picked_contracts:
        print("\nQualifying far-OTM calls (in the configured delta band, under the premium cap):")
        for contract, greeks in pop.picked_contracts:
            print(f"  ${contract.strike:.2f} exp {contract.expiry}  ${contract.mid_price:.2f}  delta {greeks.delta:.2f}")
    for note in pop.notes:
        print(f"! {note}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="options-screener", description="Screens options for cheap near-the-money contracts and far-OTM 'bound to pop' candidates."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    screen_parser = subparsers.add_parser("screen", help="Scan your whole watchlist")
    screen_parser.set_defaults(func=cmd_screen)

    analyze_parser = subparsers.add_parser("analyze", help="Full breakdown for one ticker")
    analyze_parser.add_argument("ticker", help='e.g. "AAPL"')
    analyze_parser.set_defaults(func=cmd_analyze)

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
