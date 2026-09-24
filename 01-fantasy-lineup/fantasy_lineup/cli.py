import argparse
import sys

from .client import get_week_players
from .config import load_config
from .recommend import recommend_swaps


def cmd_lineup(args: argparse.Namespace) -> None:
    config = load_config()
    players = get_week_players(config, week=args.week)
    swaps = recommend_swaps(players)

    if not swaps:
        print("No swaps recommended — your best projected players are already starting.")
        return

    print(f"{len(swaps)} suggested swap(s):\n")
    for s in swaps:
        print(
            f"[{s.slot}] Sit {s.sit.name} ({s.sit.projected_points:.1f} pts, vs {s.sit.pro_opponent})  "
            f"-> Start {s.start.name} ({s.start.projected_points:.1f} pts, vs {s.start.pro_opponent})  "
            f"(+{s.point_gain:.1f})"
        )


def cmd_roster(args: argparse.Namespace) -> None:
    config = load_config()
    players = get_week_players(config, week=args.week)
    starters = [p for p in players if not p.is_bench]
    bench = [p for p in players if p.is_bench]

    def show(group: list[object], label: str) -> None:
        print(f"-- {label} --")
        for p in sorted(group, key=lambda p: p.projected_points, reverse=True):
            print(
                f"{p.lineup_slot:<5} {p.name:<25} {p.position:<4} "
                f"vs {p.pro_opponent:<4} proj {p.projected_points:.1f}"
            )
        print()

    show(starters, "Starting")
    show(bench, "Bench")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy-lineup", description="Start/sit advice for your ESPN fantasy football team."
    )
    parser.add_argument("--week", type=int, default=None, help="NFL week (defaults to the current week)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lineup_parser = subparsers.add_parser("lineup", help="Suggest starter/bench swaps")
    lineup_parser.set_defaults(func=cmd_lineup)

    roster_parser = subparsers.add_parser("roster", help="Show your full roster with matchups and projections")
    roster_parser.set_defaults(func=cmd_roster)

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
