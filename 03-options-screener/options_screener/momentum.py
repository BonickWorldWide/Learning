from .models import MomentumResult


def _return_over(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    return (closes[-1] - closes[-1 - lookback]) / closes[-1 - lookback]


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Standard Wilder RSI, using a plain average over the window rather
    than Wilder's smoothing -- close enough for a screen, and simple enough
    to hand-verify."""
    if len(closes) <= period:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = [c for c in changes if c > 0]
    losses = [-c for c in changes if c < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def build_momentum(closes: list[float]) -> MomentumResult:
    """`closes` is daily closing prices, oldest first. Each signal is None
    when there isn't enough history yet rather than a misleading default --
    `MomentumResult.bullish_score` already skips whichever signals are
    None instead of guessing.
    """
    sma_50 = _sma(closes, 50)
    above_50sma = (closes[-1] > sma_50) if sma_50 is not None else None

    return MomentumResult(
        return_20d=_return_over(closes, 20),
        rsi_14=_rsi(closes, 14),
        above_50sma=above_50sma,
    )
