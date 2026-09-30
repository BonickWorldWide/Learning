import sys
from datetime import date, timedelta

import requests

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
DEFAULT_LOOKBACK_DAYS = 7


def fetch_finnhub_headlines(
    ticker: str, api_key: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS, count: int = 10
) -> list[str]:
    """Recent company news from Finnhub's free-tier API -- real structured
    JSON from an official source, not scraped HTML, so it's the most
    reliable of the news paths when a key is configured. Skipped entirely
    (returns []) when `api_key` is blank, the same "optional, off until
    configured" shape as SEC EDGAR -- a free key is at https://finnhub.io/register,
    no fair-access header requirement the way SEC has, just an ordinary key.

    A real run against AAPL -- one of the most heavily covered stocks that
    exists -- returned 247 articles in a single 7-day window, most of them
    market-roundup pieces that only mention AAPL in passing rather than
    being about it specifically. `count` caps this the same way every other
    source here does; sorting by `datetime` first (rather than trusting
    whatever order Finnhub happens to return) is what makes "capped" mean
    "most recent," not just "however many came first in the response."
    """
    if not api_key:
        return []

    today = date.today()
    params = {
        "symbol": ticker,
        "from": (today - timedelta(days=lookback_days)).isoformat(),
        "to": today.isoformat(),
        "token": api_key,
    }
    try:
        response = requests.get(FINNHUB_NEWS_URL, params=params, timeout=10)
        response.raise_for_status()
        articles = response.json()
    except Exception as e:
        print(f"  (couldn't fetch Finnhub news for {ticker}: {e})", file=sys.stderr)
        return []

    if not isinstance(articles, list):
        print(f"  (Finnhub returned an unexpected response shape for {ticker}: {articles})", file=sys.stderr)
        return []

    articles.sort(key=lambda a: a.get("datetime", 0), reverse=True)
    return [a["headline"] for a in articles if a.get("headline")][:count]
