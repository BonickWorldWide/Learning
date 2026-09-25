import argparse
import sys

from .client import get_week_players
from .config import load_config
from .models import PlayerReport
from .nfl_data import get_games, get_id_crosswalk, get_weekly_stats
from .recommend import build_start_over_lines, group_by_position, rank_group
from .report import build_player_reports


def cmd_matchups(args: argparse.Namespace) -> None:
    config = load_config()
    players = get_week_players(config, week=args.week)

    player_seasons = list(range(config.year - config.player_seasons_lookback + 1, config.year + 1))
    team_seasons = list(range(config.year - config.team_seasons_lookback + 1, config.year + 1))

    print(f"Fetching {len(player_seasons)} season(s) of player stats...", file=sys.stderr)
    weekly_df = get_weekly_stats(player_seasons, refresh=args.refresh_data)
    games_df = get_games(refresh=args.refresh_data)
    crosswalk = get_id_crosswalk(refresh=args.refresh_data)

    reports = build_player_reports(
        players,
        weekly_df,
        games_df,
        crosswalk,
        current_season=config.year,
        scoring=config.scoring,
        team_seasons=team_seasons,
    )

    if not reports:
        print("No QB/RB/WR/TE players found on your roster for this week.")
        return

    print(
        f"Scoring: {config.scoring}   "
        f"Player history: {min(player_seasons)}-{max(player_seasons)}   "
        f"Team tendencies: {min(team_seasons)}-{max(team_seasons)}\n"
    )
    print_player_section(reports)
    print_team_section(reports, team_seasons)
    print_recommendations(reports)


def print_player_section(reports: list[PlayerReport]) -> None:
    print("=" * 70)
    print("1. PLAYER VS OPPONENT (CAREER)")
    print("=" * 70)
    for r in reports:
        h = r.history
        print(f"\n{r.player.name} ({r.player.position}, {r.player.pro_team}) vs {h.opponent}")
        if not h.has_history:
            print("  No recorded meetings vs this opponent.")
            continue

        sample_note = "  [SMALL SAMPLE]" if h.small_sample else ""
        print(f"  Games vs opponent: {h.games_vs_opponent}{sample_note}   Career games: {h.career_games}")
        print(
            f"  PPG vs opponent: {h.ppg_vs_opponent:.1f}   "
            f"Career PPG: {h.career_ppg:.1f}   Delta: {h.ppg_delta:+.1f}"
        )
        for key, vs_val in h.stat_averages_vs_opponent.items():
            career_val = h.stat_averages_career.get(key, 0.0)
            print(f"    {key:<18} vs opp {vs_val:>6.1f}   career {career_val:>6.1f}")


def print_team_section(reports: list[PlayerReport], team_seasons: list[int]) -> None:
    span = f"{min(team_seasons)}-{max(team_seasons)}" if team_seasons else "n/a"
    print("\n" + "=" * 70)
    print(f"2. TEAM VS OPPONENT (seasons {span})")
    print("=" * 70)

    seen: set[tuple[str, str]] = set()
    for r in reports:
        t = r.team_tendency
        key = (t.team, t.opponent)
        if key in seen:
            continue
        seen.add(key)

        sample_note = "  [SMALL SAMPLE]" if t.small_sample else ""
        print(f"\n{t.team} vs {t.opponent}  ({t.games} games){sample_note}")
        if not t.has_history:
            print("  No games found in this window.")
            continue

        print(f"  Run rate: {t.run_rate:.0%}   Pass rate: {t.pass_rate:.0%}")
        points_str = f"   Avg points: {t.avg_points_for:.1f}" if t.avg_points_for is not None else ""
        print(f"  Avg rush yards: {t.avg_rush_yards:.1f}   Avg pass yards: {t.avg_pass_yards:.1f}{points_str}")
        for pos, share in t.position_volume_share.items():
            top = t.top_volume_player.get(pos, "?")
            print(f"    {pos} volume share: {share:.0%}  (top: {top})")

        c = r.continuity
        if c.head_coach_changed:
            print(f"  NOTE: head coach changed since these meetings ({', '.join(c.prior_coaches)} -> {c.current_coach})")
        if c.qb_changed:
            print(f"  NOTE: different starting QB then ({', '.join(c.prior_qbs)} -> {c.current_qb})")
        for note in c.notes:
            print(f"  NOTE: {note}")


def print_recommendations(reports: list[PlayerReport]) -> None:
    print("\n" + "=" * 70)
    print("3. START/SIT RECOMMENDATION")
    print("=" * 70)

    groups = group_by_position(reports)
    for position in sorted(groups):
        group = groups[position]
        print(f"\n-- {position} --")
        ranked = rank_group(group)
        for rp in ranked:
            print(f"  {rp.rank}. {rp.report.player.name}: {rp.summary}")
        for line in build_start_over_lines(ranked):
            print(f"  -> {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy-lineup", description="Matchup history and start/sit advice for your ESPN fantasy team."
    )
    parser.add_argument("--week", type=int, default=None, help="NFL week (defaults to the current week)")
    parser.add_argument(
        "--refresh-data", action="store_true", help="Re-download NFL stats instead of using the local cache"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    matchups_parser = subparsers.add_parser("matchups", help="Show matchup history and start/sit recommendations")
    matchups_parser.set_defaults(func=cmd_matchups)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
