from .models import HeadToHeadSummary, VenueSplit


def format_record_table(summary: HeadToHeadSummary) -> str:
    lines = [
        f"| Window | Games | {summary.team_a} W | {summary.team_b} W | Ties | "
        f"{summary.team_a} avg margin | {summary.team_b} avg margin |",
        "|---|---|---|---|---|---|---|",
    ]
    for split in (summary.all_time, summary.last_10, summary.last_20):
        lines.append(
            f"| {split.label} | {split.games} | {split.team_a_wins} | {split.team_b_wins} | "
            f"{split.ties} | {_fmt(split.avg_margin_team_a)} | {_fmt(split.avg_margin_team_b)} |"
        )
    return "\n".join(lines)


def format_venue_table(team: str, splits: dict[str, VenueSplit]) -> str:
    lines = [
        f"| {team} venue | W | L | T | Avg margin |",
        "|---|---|---|---|---|",
    ]
    for venue in ("home", "away", "neutral"):
        split = splits.get(venue)
        if split is None:
            continue
        lines.append(f"| {venue} | {split.wins} | {split.losses} | {split.ties} | {_fmt(split.avg_margin)} |")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return f"{value:+.1f}" if value is not None else "—"
