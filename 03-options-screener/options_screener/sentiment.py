import re

from .models import SentimentResult

# A small, hand-curated financial-news lexicon rather than a general-purpose
# one (VADER, etc.) -- "beat," "guidance," "upgrade" carry meaning here that
# a general lexicon has no reason to know about, and a short list anyone can
# read is the whole point of an explainable scorer.
POSITIVE_WORDS = {
    "beat", "beats", "beating", "surge", "surges", "surging", "soar", "soars", "soaring",
    "upgrade", "upgraded", "upgrades", "record", "strong", "growth", "raises", "raised",
    "raising", "outperform", "rally", "rallies", "bullish", "breakthrough", "approval",
    "approved", "partnership", "expands", "expansion", "beats-expectations", "profit",
    "profits", "gains", "gain", "wins", "win", "boost", "boosts", "optimistic", "upbeat",
}
NEGATIVE_WORDS = {
    "miss", "misses", "missing", "plunge", "plunges", "plunging", "downgrade", "downgraded",
    "downgrades", "lawsuit", "lawsuits", "recall", "recalls", "warns", "warning", "warned",
    "bearish", "weak", "weakness", "decline", "declines", "declining", "layoffs", "fraud",
    "investigation", "delay", "delayed", "cuts", "cut", "cutting", "bankruptcy", "recession",
    "loss", "losses", "slump", "slumps", "slumping", "probe", "sues", "sued", "scandal",
}

_WORD_RE = re.compile(r"[a-z-]+")


def _score_headline(headline: str) -> float:
    words = set(_WORD_RE.findall(headline.lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def _dedupe(headlines: list[str]) -> list[str]:
    """Order-preserving, case/whitespace-insensitive. Headlines now come
    from four independent sources (yfinance, Yahoo RSS, Google News,
    Finnhub) combined into one list before this ever sees it -- a real run
    showed the exact same wire story ("New Apple CEO John Ternus is
    reportedly planning layoffs...") counted twice because two sources
    both carried it. That's the same signal, not two of them; without
    this, one story getting picked up by more outlets would silently mean
    "counts more" rather than "was reported more," which isn't what
    sentiment is supposed to measure.
    """
    seen = set()
    unique = []
    for h in headlines:
        key = h.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique


def score_headlines(headlines: list[str]) -> SentimentResult:
    """Average per-headline score, -1..+1, over the *distinct* headlines
    (see `_dedupe`). Headlines with no lexicon hits score 0 (neutral) and
    still count toward `headline_count` -- silence isn't the same as a
    confirmed neutral opinion, which is what `low_confidence` is for.
    """
    headlines = _dedupe(headlines)
    if not headlines:
        return SentimentResult(score=0.0, headline_count=0)

    scores = [_score_headline(h) for h in headlines]
    positive = [h for h, s in zip(headlines, scores) if s > 0]
    negative = [h for h, s in zip(headlines, scores) if s < 0]

    return SentimentResult(
        score=sum(scores) / len(scores),
        headline_count=len(headlines),
        positive_headlines=positive,
        negative_headlines=negative,
    )
