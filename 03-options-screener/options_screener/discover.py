from .models import MomentumResult, SentimentResult


def prefilter_score(momentum: MomentumResult, sentiment: SentimentResult | None = None) -> float:
    """The cheap half of a two-stage scan -- momentum and (optionally)
    sentiment, no option chain and no news fetch involved, so this can run
    over hundreds of tickers before the expensive stage (fetching each
    one's option chain, and only then real multi-source news) narrows down
    to the handful actually worth it. Equal-weighted, same explainability
    principle as screener.py's full composite score.

    `sentiment` is optional. A real 503-ticker run showed why: fetching
    full news (four sources, with fallbacks) for every ticker just to rank
    them was the single biggest cost in the whole scan, and it couldn't
    have changed the ranking anyway -- a neutral sentiment score adds the
    exact same constant to every ticker, so relative order comes entirely
    from momentum regardless. `cli.py`'s real prefilter loop no longer
    fetches news at all; it defers that to the expensive stage, for only
    the ~15 tickers that make the shortlist. None is treated as neutral
    (0.0) rather than requiring every caller to construct a fake
    SentimentResult just to say "no data yet."
    """
    sentiment_score = sentiment.score if sentiment is not None else 0.0
    sentiment_component = (sentiment_score + 1) / 2
    return (momentum.bullish_score + sentiment_component) / 2


def shortlist(scored: list[tuple[str, float]], top_n: int = 15) -> list[str]:
    """Highest prefilter score first, ticker symbols only -- what decides
    which tickers are worth the expensive option-chain fetch."""
    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    return [ticker for ticker, _ in ranked[:top_n]]
