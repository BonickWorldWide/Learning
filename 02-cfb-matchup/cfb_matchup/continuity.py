from .models import ContinuityFlags


def build_continuity(team: str, notes: list[str] | None = None) -> ContinuityFlags:
    """Continuity flags for one team -- things that make older history less
    reliable: a new head coach, a coordinator change, a conference move, a
    new starting QB, heavy transfer-portal turnover.

    Unlike the fantasy-football project's version of this idea, there's no
    free public dataset of FBS coaching history or transfer-portal activity
    reachable from here, so this doesn't try to detect anything
    automatically -- it's a pass-through for notes you supply yourself. Pass
    them in via CLI flags or a small notes file; see the README.
    """
    return ContinuityFlags(team=team, notes=list(notes or []))
