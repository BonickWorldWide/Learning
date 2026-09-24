import argparse
from datetime import date

from .models import Round
from .stats import summarize
from .storage import load_rounds, save_round


def cmd_add(args: argparse.Namespace) -> None:
    played_on = date.fromisoformat(args.date) if args.date else date.today()
    round_ = Round(course=args.course, par=args.par, strokes=args.strokes, played_on=played_on)
    save_round(round_)
    sign = "+" if round_.to_par >= 0 else ""
    print(f"Saved: {round_.played_on} at {round_.course} — {round_.strokes} ({sign}{round_.to_par})")


def cmd_list(args: argparse.Namespace) -> None:
    rounds = sorted(load_rounds(), key=lambda r: r.played_on)
    if not rounds:
        print("No rounds logged yet. Add one with: golf-tracker add ...")
        return
    for r in rounds:
        sign = "+" if r.to_par >= 0 else ""
        print(f"{r.played_on}  {r.course:<25} par {r.par:<3} strokes {r.strokes:<3} ({sign}{r.to_par})")


def cmd_stats(args: argparse.Namespace) -> None:
    summary = summarize(load_rounds())
    if summary is None:
        print("No rounds logged yet. Add one with: golf-tracker add ...")
        return
    print(f"Rounds played:    {summary.rounds_played}")
    print(f"Average strokes:  {summary.average_strokes:.1f}")
    print(f"Average to par:   {summary.average_to_par:+.1f}")
    print(f"Best round:       {summary.best_round.strokes} at {summary.best_round.course} ({summary.best_round.played_on})")
    print(f"Worst round:      {summary.worst_round.strokes} at {summary.worst_round.course} ({summary.worst_round.played_on})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="golf-tracker", description="Track and review your golf rounds.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Log a round")
    add_parser.add_argument("--course", required=True, help="Course name")
    add_parser.add_argument("--par", type=int, required=True, help="Course par")
    add_parser.add_argument("--strokes", type=int, required=True, help="Your total strokes")
    add_parser.add_argument("--date", help="Date played, YYYY-MM-DD (defaults to today)")
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser("list", help="List logged rounds")
    list_parser.set_defaults(func=cmd_list)

    stats_parser = subparsers.add_parser("stats", help="Show summary stats")
    stats_parser.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
