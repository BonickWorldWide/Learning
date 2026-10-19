from .models import OptionContract, VolumeSignal

# How many trailing trading days count as "recent" vs. the longer
# "baseline" window relative_volume compares it against.
RELATIVE_VOLUME_RECENT_DAYS = 5
RELATIVE_VOLUME_BASELINE_DAYS = 20


def relative_volume(
    volumes: list[int], recent: int = RELATIVE_VOLUME_RECENT_DAYS, baseline: int = RELATIVE_VOLUME_BASELINE_DAYS
) -> float | None:
    """Average daily trading volume over the most recent `recent` days,
    divided by the average over the `baseline` days before that -- how
    much MORE (or less) this stock is trading than its own normal pace.
    1.0 is "trading exactly like usual"; 2.0 is "twice the normal volume."

    This is a different signal from this module's own
    unusual_volume_contracts: that one looks at a single *option
    contract's* volume against its open interest, which a single trader
    opening 100 contracts against 100 open interest on an otherwise dead
    name can trivially trip. This looks at the *stock itself* trading more
    than usual -- real, broad market interest, not one options order.

    None when there isn't `recent + baseline` days of volume history, or
    the baseline average is zero (can't compute a meaningful ratio against
    no volume at all).
    """
    needed = recent + baseline
    if len(volumes) < needed:
        return None
    recent_avg = sum(volumes[-recent:]) / recent
    baseline_avg = sum(volumes[-needed:-recent]) / baseline
    if baseline_avg <= 0:
        return None
    return recent_avg / baseline_avg


def unusual_volume_contracts(
    contracts: list[OptionContract], min_volume: int = 100, min_open_interest: int = 50, threshold: float = 1.0
) -> list[VolumeSignal]:
    """Today's volume vs. standing open interest, per contract -- the
    classic "unusual options activity" heuristic: volume that alone
    exceeds everyone who already held a position suggests new money just
    showed up, not existing holders trading among themselves.

    `min_volume` filters out contracts where a handful of contracts against
    zero open interest would otherwise look like an infinite ratio -- that's
    noise on an illiquid strike, not a signal. `min_open_interest` closes a
    related gap: `volume=100, open_interest=100` clears `min_volume` and
    hits the ratio threshold exactly, but a hundred contracts total open on
    a name is itself a sign nobody's really trading it -- one order on a
    thin, barely-open strike, not real conviction. Requiring some standing
    open interest first means the ratio is measuring a surge against an
    already-real market, not against almost nothing.
    """
    signals = []
    for c in contracts:
        if c.volume < min_volume or c.open_interest < min_open_interest:
            continue
        ratio = c.volume / max(c.open_interest, 1)
        signals.append(VolumeSignal(contract=c, volume_to_oi=ratio))

    return sorted((s for s in signals if s.volume_to_oi >= threshold), key=lambda s: s.volume_to_oi, reverse=True)
