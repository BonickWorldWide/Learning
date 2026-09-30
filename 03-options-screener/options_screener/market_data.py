import io
import sys
import time
import xml.etree.ElementTree as ElementTree
from datetime import date, datetime

import pandas as pd
import requests
import yfinance as yf

from .models import OptionContract
from .option_rows import row_to_contract

# yfinance's own get_news() swallows a bad response internally (a JSON
# decode failure is logged, not raised) and just returns an empty list --
# so this file can't catch an exception to retry, only notice the result
# came back empty. One retry after a real pause is cheap insurance against
# a transient burst.
NEWS_RETRY_DELAY_SECONDS = 2.0

# Isolated single-ticker testing (no burst beforehand) still came back with
# zero articles -- ruling out a throttle as the sole explanation.
# get_news() sends an authenticated POST that needs a Yahoo session cookie
# + crumb (yfinance's data.py); the option-chain and price-history calls
# that work fine are plain GETs that don't need one. Crumb/cookie
# acquisition for Yahoo's newer endpoints is a widely-reported pain point
# with yfinance generally, not something specific to this code. Yahoo's
# older RSS feed is a plain, unauthenticated GET -- a structurally simpler
# fallback that doesn't depend on that same session machinery, tried when
# get_news() comes up empty. Unverified against live data either way.
YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

# A third fallback, tried after both Yahoo paths come up empty. Google
# News aggregates thousands of publishers rather than being tied to one,
# and needs no key or session -- but a bare single-letter ticker ("A" for
# Agilent, "V" for Visa) is a nearly useless search query, so this is
# passed the company name when one is available (see fetch_sp500_tickers)
# and only falls back to the ticker alone otherwise.
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

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


def _fetch_rss_headlines(ticker: str) -> list[str]:
    url = YAHOO_RSS_URL.format(ticker=ticker)
    try:
        response = requests.get(url, headers={"User-Agent": _BROWSER_USER_AGENT}, timeout=10)
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
    except Exception as e:
        print(f"  (RSS fallback also failed for {ticker}: {e})", file=sys.stderr)
        return []
    return [title for item in root.iter("item") if (title := item.findtext("title"))]


def _fetch_google_news_headlines(ticker: str, company_name: str | None) -> list[str]:
    query = f"{company_name} stock" if company_name else f"{ticker} stock"
    try:
        response = requests.get(
            GOOGLE_NEWS_RSS_URL,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            headers={"User-Agent": _BROWSER_USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
    except Exception as e:
        print(f"  (Google News fallback also failed for {ticker}: {e})", file=sys.stderr)
        return []
    return [title for item in root.iter("item") if (title := item.findtext("title"))]


def fetch_news_headlines(ticker: str, count: int = 10, company_name: str | None = None) -> list[str]:
    """Recent headline titles, tried three ways in order:

    1. yfinance's own news feed (one retry on empty, see
       NEWS_RETRY_DELAY_SECONDS above). Yahoo's JSON schema has also
       changed shape across yfinance versions (a flat "title" key, then a
       nested "content.title"); this tries both rather than assuming one.
    2. Yahoo's older RSS feed if that comes back with nothing usable --
       see YAHOO_RSS_URL above for why that's a meaningfully different
       path, not just a second attempt at the same thing.
    3. Google News RSS if that *also* comes back empty -- broader
       multi-publisher coverage as a last resort, using `company_name`
       for a real search query when the caller has one (discover.py does,
       from the same S&P 500 table it already fetched tickers from).
    """
    articles = _fetch_raw_news(ticker, count)
    if not articles:
        time.sleep(NEWS_RETRY_DELAY_SECONDS)
        articles = _fetch_raw_news(ticker, count)

    headlines = []
    if articles:
        for article in articles:
            title = article.get("title") or (article.get("content") or {}).get("title")
            if title:
                headlines.append(title)
        if not headlines:
            # Articles came back, but nothing matched either known title
            # shape -- printing the real keys is how the next schema
            # change actually gets fixed instead of guessed at again.
            print(
                f"  (got {len(articles)} raw article(s) for {ticker} but extracted 0 titles -- "
                f"first article's keys: {list(articles[0].keys())})",
                file=sys.stderr,
            )

    if not headlines:
        headlines = _fetch_rss_headlines(ticker)

    if not headlines:
        headlines = _fetch_google_news_headlines(ticker, company_name)

    if not headlines:
        print(
            f"  (0 headlines for {ticker} from yfinance's news feed, the Yahoo RSS fallback, "
            "and the Google News fallback)",
            file=sys.stderr,
        )

    return headlines[:count]


def fetch_sp500_tickers() -> tuple[list[str], dict[str, str]]:
    """Wikipedia's own, always-current S&P 500 constituent table -- no
    bundled list here to go stale as the index is reconstituted. A ticker
    with a dot (BRK.B) is rewritten with a hyphen (BRK-B), which is how
    Yahoo Finance -- and so `yfinance` -- actually names it; passing the
    dotted form straight through would fail to find that ticker at all.

    Also returns a ticker -> company name map (Wikipedia's "Security"
    column) -- fetching this table is the one place a real company name is
    available for free, and `fetch_news_headlines`'s Google News fallback
    needs one: a bare single-letter ticker like "A" or "V" is a nearly
    useless search query on its own.
    """
    try:
        response = requests.get(SP500_WIKIPEDIA_URL, headers={"User-Agent": _BROWSER_USER_AGENT}, timeout=10)
        response.raise_for_status()
        table = pd.read_html(io.StringIO(response.text))[0]
    except Exception as e:
        print(f"  (couldn't fetch the S&P 500 ticker list: {e})", file=sys.stderr)
        return [], {}

    tickers = [s.replace(".", "-") for s in table["Symbol"].tolist()]
    names = {t: name for t, name in zip(tickers, table["Security"].tolist())}
    return tickers, names
