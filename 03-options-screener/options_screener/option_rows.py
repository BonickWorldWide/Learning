import math

from .models import OptionContract


def _clean(value, default):
    """NaN and None both mean "no data" in a pandas-sourced options row --
    yfinance's numeric columns come back as NaN, not None, for a contract
    with nothing reported that day (no trades, no open interest), and
    `NaN or default` never falls through to `default` because NaN is
    truthy in Python. That's what actually broke a real run: every
    contract with zero volume raised "cannot convert float NaN to
    integer" instead of quietly defaulting to zero.
    """
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    return value


def row_to_contract(ticker: str, option_type: str, row, days_to_expiry: int, expiry: str) -> OptionContract | None:
    """None if the row has no implied volatility at all. Every other field
    (volume, open interest, bid/ask, last price) defaults sensibly to zero
    when missing, but there's no sensible stand-in for "we don't know this
    contract's volatility" -- faking a 0 would tell the model this contract
    has literally no time value, which is a real, meaningful claim (and one
    `greeks.py` already treats specially), not the absence of one.
    """
    iv = _clean(row.impliedVolatility, None)
    if iv is None:
        return None

    return OptionContract(
        ticker=ticker,
        option_type=option_type,
        strike=float(row.strike),
        expiry=expiry,
        days_to_expiry=days_to_expiry,
        bid=float(_clean(row.bid, 0.0)),
        ask=float(_clean(row.ask, 0.0)),
        last_price=float(_clean(row.lastPrice, 0.0)),
        volume=int(_clean(row.volume, 0)),
        open_interest=int(_clean(row.openInterest, 0)),
        implied_volatility=float(iv),
    )
