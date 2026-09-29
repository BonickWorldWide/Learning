import io
import sys
import time
from datetime import date, datetime

import pandas as pd
import requests
import yfinance as yf

from .models import OptionContract
from .option_rows import row_to_contract

# yfinance's own get_news() swallows a bad response internally (a JSON
# decode failure is logged, not raised) and just returns an empty list --
# so this file can't catch an exception to retry, only notice the result
# came back empty. A real 503-ticker run hit exactly this for roughly the
# back half of the alphabet, all at once, midway through the run: the
# classic shape of a burst throttle, not per-ticker bad luck. One retry
# after a real pause is cheap insurance against that; it is not verified
# to fix it, since it can't be tested against a live throttle from here.
NEWS_RETRY_DELAY_SECONDS = 2.0

SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Wikipedia returns a 403 to pandas.read_html's own request -- it (like a
# lot of sites) rejects whatever generic User-Agent urllib sends by
# default. Fetching the page ourselves with a browser-like one first, then
# handing pandas the HTML instead of the URL, is the standard fix.
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# The nearest N expiries only -- a "cheap near-the-money" or "far OTM
# lottery ticket" screen cares about contracts a few weeks to a couple
# months out, not LEAPS two years away, and pulling every expiry multiplies
# the request count for nothing this screen would ever pick.
DEFAULT_MAX_EXPIRIES = 4


def _days_to_expiry(expiry: str) -> int:
    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    return (expiry_date - date.today()).days


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
            calls.extend(
                c for c in (row_to_contract(ticker, "call", row, dte, expiry) for row in chain.calls.itertuples())
                if c is not None
            )
        if chain.puts is not None:
            puts.extend(
                c for c in (row_to_contract(ticker, "put", row, dte, expiry) for row in chain.puts.itertuples())
                if c is not None
            )

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


def _fetch_raw_news(ticker: str, count: int) -> list:
    t = yf.Ticker(ticker)
    try:
        return t.get_news(count=count)
    except Exception as e:
        print(f"  (couldn't fetch news for {ticker}: {e})", file=sys.stderr)
        return []


def fetch_news_headlines(ticker: str, count: int = 10) -> list[str]:
    """Recent headline titles. Yahoo's news schema has changed shape across
    yfinance versions (a flat "title" key, then a nested "content.title")
    -- this tries both rather than assuming one, since a schema change here
    should mean fewer headlines found, not a crash.
    """
    articles = _fetch_raw_news(ticker, count)
    if not articles:
        # Could be a real "no recent news," or the throttle described
        # above -- one retry after a real pause costs little either way.
        time.sleep(NEWS_RETRY_DELAY_SECONDS)
        articles = _fetch_raw_news(ticker, count)
        if not articles:
            print(f"  (0 news articles for {ticker} even after a retry -- Yahoo may be throttling)", file=sys.stderr)
            return []

    headlines = []
    for article in articles:
        title = article.get("title") or (article.get("content") or {}).get("title")
        if title:
            headlines.append(title)

    if not headlines:
        # Articles came back, but nothing matched either known title shape
        # -- printing the real keys is how the next schema change actually
        # gets fixed instead of guessed at again.
        print(
            f"  (got {len(articles)} raw article(s) for {ticker} but extracted 0 titles -- "
            f"first article's keys: {list(articles[0].keys())})",
            file=sys.stderr,
        )
    return headlines


def fetch_sp500_tickers() -> list[str]:
    """Wikipedia's own, always-current S&P 500 constituent table -- no
    bundled list here to go stale as the index is reconstituted. A ticker
    with a dot (BRK.B) is rewritten with a hyphen (BRK-B), which is how
    Yahoo Finance -- and so `yfinance` -- actually names it; passing the
    dotted form straight through would fail to find that ticker at all.
    """
    try:
        response = requests.get(SP500_WIKIPEDIA_URL, headers={"User-Agent": _BROWSER_USER_AGENT}, timeout=10)
        response.raise_for_status()
        tables = pd.read_html(io.StringIO(response.text))
        symbols = tables[0]["Symbol"].tolist()
    except Exception as e:
        print(f"  (couldn't fetch the S&P 500 ticker list: {e})", file=sys.stderr)
        return []
    return [s.replace(".", "-") for s in symbols]
