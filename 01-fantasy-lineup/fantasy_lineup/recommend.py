from dataclasses import dataclass

from .models import PlayerReport


@dataclass
class RankedPlayer:
    report: PlayerReport
    rank: int
    summary: str


def group_by_position(reports: list[PlayerReport]) -> dict[str, list[PlayerReport]]:
    groups: dict[str, list[PlayerReport]] = {}
    for r in reports:
        groups.setdefault(r.player.position, []).append(r)
    return groups


def rank_group(reports: list[PlayerReport]) -> list[RankedPlayer]:
    """Rank same-position players by their matchup-adjusted edge.

    Players with no history vs this opponent rank last (a conservative
    default — no evidence of an edge either way beats claiming one).
    """
    ordered = sorted(reports, key=_sort_key, reverse=True)
    return [RankedPlayer(report=r, rank=i + 1, summary=_summarize(r)) for i, r in enumerate(ordered)]


def build_start_over_lines(ranked: list[RankedPlayer]) -> list[str]:
    lines = []
    for higher, lower in zip(ranked, ranked[1:]):
        lines.append(f"Start {higher.report.player.name} over {lower.report.player.name}: {higher.summary}")
    return lines


def _sort_key(report: PlayerReport) -> float:
    delta = report.history.ppg_delta
    return delta if delta is not None else float("-inf")


def _summarize(report: PlayerReport) -> str:
    history = report.history
    parts = []

    if history.ppg_delta is not None:
        parts.append(
            f"{history.ppg_delta:+.1f} pts/g vs career in this matchup ({history.games_vs_opponent}g)"
        )
    else:
        parts.append("no history vs this opponent")

    lean = _tendency_clause(report)
    if lean:
        parts.append(lean)

    summary = "; ".join(parts)
    caveats = _caveats(report)
    if caveats:
        summary += f" [{', '.join(caveats)}]"
    return summary


def _tendency_clause(report: PlayerReport) -> str | None:
    tendency = report.team_tendency
    position = report.player.position
    # A "leans run/pass" claim from 1-2 games is noise, not a tendency —
    # better to say nothing than to cite it as a reason to start someone.
    if not tendency.has_history or tendency.small_sample:
        return None

    if position == "RB" and tendency.run_rate is not None and tendency.run_rate >= 0.55:
        return f"{tendency.team} leans run ({tendency.run_rate:.0%}) vs this defense"
    if position in ("WR", "TE") and tendency.pass_rate is not None and tendency.pass_rate >= 0.60:
        return f"{tendency.team} leans pass ({tendency.pass_rate:.0%}) vs this defense"
    return None


def _caveats(report: PlayerReport) -> list[str]:
    caveats = []
    if report.history.small_sample and report.history.has_history:
        caveats.append(f"small sample: {report.history.games_vs_opponent}g")
    if report.continuity.head_coach_changed:
        caveats.append("new HC since these games")
    if report.continuity.qb_changed:
        caveats.append("different starting QB then")
    caveats.extend(report.continuity.notes)
    return caveats
