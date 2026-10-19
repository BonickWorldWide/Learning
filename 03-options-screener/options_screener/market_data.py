import io
import sys
import xml.etree.ElementTree as ElementTree
from datetime import date, datetime

import pandas as pd
import requests
import yfinance as yf

from .models import OptionContract
from .option_rows import row_to_contract

# get_news() was originally retried once after a pause, on the theory that
# an empty result meant a transient throttle. Real testing disproved that:
# an isolated single-ticker call, with no burst beforehand at all, still
# came back empty. The real cause (below) is a structural auth problem, not
# a transient one -- retrying the same broken cookie/crumb flow 2 seconds
# later can't fix it, and doing that across a 500-ticker prefilter loop
# was costing ~1000s (500 x 2s) for a retry that never once helped in
# testing. Removed rather than shortened, since there's no evidence any
# delay here ever changes the outcome.
#
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

# Mainstream US exchanges where equity options commonly trade -- deliberately
# excludes Yahoo's OTC/pink-sheet codes (PNK, OQB, OQX) and NYSE Arca (PCX,
# almost entirely ETFs): those rarely have a real listed option chain and
# carry far higher liquidity/counterparty risk, which doesn't fit a tool
# built around actually buying contracts.
US_OPTIONABLE_EXCHANGES = ["NMS", "NGM", "NCM", "NYQ", "ASE"]

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


def fetch_price_history(ticker: str, period: str = "1y") -> tuple[list[float], list[int]]:
    """Daily closes and daily volumes, both oldest first, from the same
    single call -- what momentum.py and volatility.py need for closes, and
    volume_signal.relative_volume needs for volumes. Volume used to be
    fetched and immediately discarded here; the real fix for "the screen
    picks far-OTM calls on stocks that barely ever move" needed both the
    realized-volatility signal (built from closes, already here) and a
    real stock-trading-volume signal, and the data for the second one was
    already sitting in this same response the whole time.
    """
    t = yf.Ticker(ticker)
    try:
        hist = t.history(period=period)
    except Exception as e:
        print(f"  (couldn't fetch price history for {ticker}: {e})", file=sys.stderr)
        return [], []
    if hist.empty:
        return [], []
    return hist["Close"].tolist(), hist["Volume"].tolist()


def fetch_seasonal_history(ticker: str, years: int = 5) -> tuple[list[date], list[float]]:
    """Dates and daily closes over `years` years, for seasonality.py's
    monthly_returns_by_year -- a deliberately separate, longer fetch from
    fetch_price_history's default 1-year window. A single year of history
    can show at most one occurrence of any given calendar month, which
    seasonal_bias can never trust (MIN_YEARS_FOR_SEASONAL_SIGNAL requires
    several) -- so this is its own request, made only for the handful of
    tickers that reach the expensive analysis stage, never the full
    prefilter universe.
    """
    t = yf.Ticker(ticker)
    try:
        hist = t.history(period=f"{years}y")
    except Exception as e:
        print(f"  (couldn't fetch seasonal history for {ticker}: {e})", file=sys.stderr)
        return [], []
    if hist.empty:
        return [], []
    dates = [ts.date() for ts in hist.index]
    return dates, hist["Close"].tolist()


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

    1. yfinance's own news feed. Yahoo's JSON schema has also changed
       shape across yfinance versions (a flat "title" key, then a nested
       "content.title"); this tries both rather than assuming one.
    2. Yahoo's older RSS feed if that comes back with nothing usable --
       see YAHOO_RSS_URL above for why that's a meaningfully different
       path, not just a second attempt at the same thing.
    3. Google News RSS if that *also* comes back empty -- broader
       multi-publisher coverage as a last resort, using `company_name`
       for a real search query when the caller has one (discover.py does,
       from the same S&P 500 table it already fetched tickers from).
    """
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


def fetch_cheap_volatile_universe(
    max_price: float, min_avg_volume: float, min_beta: float, count: int = 250
) -> tuple[list[str], dict[str, str]]:
    """Tickers from Yahoo's own screener (`yf.screen`/`yf.EquityQuery`) --
    cheap, liquid, volatile names that `fetch_sp500_tickers` can never
    contain at all, however good the scoring downstream is. Direct user
    feedback: "I see other stocks like redwire (RDW) that are 15 cents a
    call for a $12.50/share... so many stocks out there that the tool
    should be combing through" -- RDW isn't in the S&P 500, so no amount of
    tuning `discover`'s signals could ever surface it; the universe itself
    was the gap, not the scoring.

    This is one request (or a few, if `count` exceeds Yahoo's 250-per-call
    cap and pagination is added later), not one per ticker: Yahoo's
    screener backend does the price/volume/beta filtering server side, so
    what comes back is already a cheap, pre-qualified universe rather than
    something this tool has to fetch 500+ individual price histories to
    build itself the way the S&P 500 path does.

    `beta` (volatility relative to the market) stands in for realized
    volatility here -- a real per-stock realized-volatility fetch is
    exactly the per-ticker cost this exists to avoid; the cheap prefilter
    stage downstream still computes and floors on the real
    `realized_volatility` once price history is fetched for ranking.
    """
    query = yf.EquityQuery(
        "and",
        [
            yf.EquityQuery("eq", ["region", "us"]),
            yf.EquityQuery("is-in", ["exchange", *US_OPTIONABLE_EXCHANGES]),
            yf.EquityQuery("lt", ["intradayprice", max_price]),
            yf.EquityQuery("gt", ["avgdailyvol3m", min_avg_volume]),
            yf.EquityQuery("gt", ["beta", min_beta]),
        ],
    )
    try:
        result = yf.screen(query, size=min(count, 250), sortField="avgdailyvol3m", sortAsc=False)
    except Exception as e:
        print(f"  (couldn't fetch the cheap/volatile screener universe: {e})", file=sys.stderr)
        return [], {}

    tickers: list[str] = []
    names: dict[str, str] = {}
    for quote in result.get("quotes", []):
        symbol = quote.get("symbol")
        if not symbol:
            continue
        tickers.append(symbol)
        name = quote.get("shortName") or quote.get("longName")
        if name:
            names[symbol] = name
    return tickers, names


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
