from .models import MomentumResult, SentimentResult


def prefilter_score(momentum: MomentumResult, sentiment: SentimentResult) -> float:
    """The cheap half of a two-stage scan -- momentum and sentiment only,
    no option chain involved, so this can run over hundreds of tickers
    before the expensive stage (fetching each one's option chain) narrows
    down to the handful actually worth it. Equal-weighted, same
    explainability principle as screener.py's full composite score.
    """
    sentiment_component = (sentiment.score + 1) / 2
    return (momentum.bullish_score + sentiment_component) / 2


def shortlist(scored: list[tuple[str, float]], top_n: int = 15) -> list[str]:
    """Highest prefilter score first, ticker symbols only -- what decides
    which tickers are worth the expensive option-chain fetch."""
    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    return [ticker for ticker, _ in ranked[:top_n]]
