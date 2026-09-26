from .models import OptionContract, VolumeSignal


def unusual_volume_contracts(
    contracts: list[OptionContract], min_volume: int = 100, threshold: float = 1.0
) -> list[VolumeSignal]:
    """Today's volume vs. standing open interest, per contract -- the
    classic "unusual options activity" heuristic: volume that alone
    exceeds everyone who already held a position suggests new money just
    showed up, not existing holders trading among themselves.

    `min_volume` filters out contracts where a handful of contracts against
    zero open interest would otherwise look like an infinite ratio -- that's
    noise on an illiquid strike, not a signal.
    """
    signals = []
    for c in contracts:
        if c.volume < min_volume:
            continue
        ratio = c.volume / max(c.open_interest, 1)
        signals.append(VolumeSignal(contract=c, volume_to_oi=ratio))

    return sorted((s for s in signals if s.volume_to_oi >= threshold), key=lambda s: s.volume_to_oi, reverse=True)
