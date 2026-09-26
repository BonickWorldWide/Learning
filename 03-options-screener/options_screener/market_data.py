import sys
from datetime import date, datetime

import pandas as pd
import yfinance as yf

from .models import OptionContract

SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# The nearest N expiries only -- a "cheap near-the-money" or "far OTM
# lottery ticket" screen cares about contracts a few weeks to a couple
# months out, not LEAPS two years away, and pulling every expiry multiplies
# the request count for nothing this screen would ever pick.
DEFAULT_MAX_EXPIRIES = 4


def _days_to_expiry(expiry: str) -> int:
    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    return (expiry_date - date.today()).days


def _row_to_contract(ticker: str, option_type: str, row, days_to_expiry: int, expiry: str) -> OptionContract:
    return OptionContract(
        ticker=ticker,
        option_type=option_type,
        strike=float(row.strike),
        expiry=expiry,
        days_to_expiry=days_to_expiry,
        bid=float(row.bid or 0),
        ask=float(row.ask or 0),
        last_price=float(row.lastPrice or 0),
        volume=int(row.volume or 0),
        open_interest=int(row.openInterest or 0),
        implied_volatility=float(row.impliedVolatility or 0),
    )


def fetch_option_chain(
    ticker: str, max_expiries: int = DEFAULT_MAX_EXPIRIES
) -> tuple[list[OptionContract], list[OptionContract], float | None]:
    """Calls, puts, and the spot price yfinance reported alongside them --
    one call per expiry (yfinance's API is per-expiry, there's no bulk
    endpoint), so `max_expiries` is directly the number of requests this
    makes.
    """
    t = yf.Ticker(ticker)
    calls: list[OptionContract] = []
    puts: list[OptionContract] = []
    spot = None

    try:
        expiries = t.options[:max_expiries]
    except Exception as e:
        print(f"  (couldn't fetch expiries for {ticker}: {e})", file=sys.stderr)
        return [], [], None

    for expiry in expiries:
        try:
            chain = t.option_chain(expiry)
        except Exception as e:
            print(f"  (couldn't fetch {expiry} chain for {ticker}: {e})", file=sys.stderr)
            continue

        if spot is None and chain.underlying:
            spot = chain.underlying.get("regularMarketPrice")

        dte = _days_to_expiry(expiry)
        if chain.calls is not None:
            calls.extend(_row_to_contract(ticker, "call", row, dte, expiry) for row in chain.calls.itertuples())
        if chain.puts is not None:
            puts.extend(_row_to_contract(ticker, "put", row, dte, expiry) for row in chain.puts.itertuples())

    return calls, puts, spot


def fetch_price_history(ticker: str, period: str = "1y") -> list[float]:
    """Daily closes, oldest first -- what momentum.py needs."""
    t = yf.Ticker(ticker)
    try:
        hist = t.history(period=period)
    except Exception as e:
        print(f"  (couldn't fetch price history for {ticker}: {e})", file=sys.stderr)
        return []
    if hist.empty:
        return []
    return hist["Close"].tolist()


def fetch_news_headlines(ticker: str, count: int = 10) -> list[str]:
    """Recent headline titles. Yahoo's news schema has changed shape across
    yfinance versions (a flat "title" key, then a nested "content.title")
    -- this tries both rather than assuming one, since a schema change here
    should mean fewer headlines found, not a crash.
    """
    t = yf.Ticker(ticker)
    try:
        articles = t.get_news(count=count)
    except Exception as e:
        print(f"  (couldn't fetch news for {ticker}: {e})", file=sys.stderr)
        return []

    headlines = []
    for article in articles:
        title = article.get("title") or (article.get("content") or {}).get("title")
        if title:
            headlines.append(title)
    return headlines


def fetch_sp500_tickers() -> list[str]:
    """Wikipedia's own, always-current S&P 500 constituent table -- no
    bundled list here to go stale as the index is reconstituted. A ticker
    with a dot (BRK.B) is rewritten with a hyphen (BRK-B), which is how
    Yahoo Finance -- and so `yfinance` -- actually names it; passing the
    dotted form straight through would fail to find that ticker at all.
    """
    try:
        tables = pd.read_html(SP500_WIKIPEDIA_URL)
        symbols = tables[0]["Symbol"].tolist()
    except Exception as e:
        print(f"  (couldn't fetch the S&P 500 ticker list: {e})", file=sys.stderr)
        return []
    return [s.replace(".", "-") for s in symbols]
