import argparse
import sys

from .analysis import MatchupReport, build_matchup_report
from .cfbd_client import fetch_recent_universe, fetch_sp_rating, fetch_team_games
from .config import load_config
from .h2h import head_to_head_games, historical_over_rate
from .models import Game, TeamRecentForm
from .tables import format_record_table, format_venue_table


def cmd_matchup(args: argparse.Namespace) -> None:
    config = load_config()
    if not config.api_key:
        raise ValueError(
            "No CollegeFootballData.com API key found. Set the CFBD_API_KEY "
            'environment variable, or add "api_key" to config.json. '
            "Get a free key at https://collegefootballdata.com/key ."
        )

    team_a, team_b = args.team_a, args.team_b
    current_year = args.year

    h2h_seasons = list(range(current_year - config.h2h_seasons_back, current_year + 1))
    recent_seasons = list(range(current_year - config.recent_seasons + 1, current_year + 1))

    print(f"Fetching {len(h2h_seasons)} seasons of head-to-head history...", file=sys.stderr)
    h2h_games = fetch_team_games(config.api_key, team_a, h2h_seasons)

    print("Fetching recent-form data for both teams and their opponents...", file=sys.stderr)
    recent_games = fetch_recent_universe(config.api_key, team_a, team_b, recent_seasons)

    sp_a = sp_b = None
    if config.use_sp_plus:
        print("Fetching SP+ ratings...", file=sys.stderr)
        sp_a = fetch_sp_rating(config.api_key, team_a, current_year)
        sp_b = fetch_sp_rating(config.api_key, team_b, current_year)

    report = build_matchup_report(
        h2h_games,
        recent_games,
        team_a,
        team_b,
        recent_seasons,
        n_simulations=config.n_simulations,
        home_team=args.home_team,
        neutral_site=args.neutral_site,
        sp_rating_a=sp_a,
        sp_rating_b=sp_b,
        notes_a=args.note_a,
        notes_b=args.note_b,
    )

    print_report(report, recent_seasons, h2h_games, team_a, team_b)


def print_report(
    report: MatchupReport, recent_seasons: list[int], h2h_games: list[Game], team_a: str, team_b: str
) -> None:
    h2h = report.h2h

    print("=" * 70)
    print("1. HEAD-TO-HEAD HISTORY")
    print("=" * 70)
    print()
    print(format_record_table(h2h))
    print()
    print(format_venue_table(h2h.team_a, h2h.team_a_venue_splits))
    print()
    print(format_venue_table(h2h.team_b, h2h.team_b_venue_splits))
    print()
    if h2h.longest_streak_team:
        print(f"Longest streak: {h2h.longest_streak_team} won {h2h.longest_streak_len} in a row")
    if h2h.current_streak_team:
        print(f"Current streak: {h2h.current_streak_team} has won {h2h.current_streak_len} in a row")
    if h2h.avg_combined_points is not None:
        print(f"Avg combined points: {h2h.avg_combined_points:.1f}")
        meetings = head_to_head_games(h2h_games, team_a, team_b)
        projected_total = report.simulation.projected_total
        over_rate = historical_over_rate(meetings, projected_total)
        if over_rate is not None:
            print(
                f"Historically, {over_rate:.0%} of these meetings went over "
                f"the model's projected total of {projected_total:.1f}"
            )
    if h2h.rarely_play:
        print(f"[LOW CONFIDENCE] Only {h2h.all_time.games} all-time meeting(s) between these teams.")

    print("\n" + "=" * 70)
    print("2. RECENT CONTEXT")
    print("=" * 70)
    span = f"{min(recent_seasons)}-{max(recent_seasons)}"
    print(f"\nSeasons: {span}\n")
    _print_recent_form(report.form_a)
    print()
    _print_recent_form(report.form_b)

    if report.common_opponent_results:
        print(f"\nCommon opponents ({len(report.common_opponent_results)}):")
        for r in report.common_opponent_results:
            a_result = "W" if r.team_a_won else "L"
            b_result = "W" if r.team_b_won else "L"
            print(
                f"  vs {r.opponent}: {h2h.team_a} {a_result} {r.team_a_score}-{r.team_a_opp_score}   "
                f"{h2h.team_b} {b_result} {r.team_b_score}-{r.team_b_opp_score}"
            )
    else:
        print("\nNo common opponents found in this window.")

    print("\n" + "=" * 70)
    print("3. SIMULATED GAME (10,000 trials)")
    print("=" * 70)
    sim = report.simulation
    print(f"\n{sim.team_a} win probability: {sim.team_a_win_prob:.1%}  (moneyline {sim.team_a_moneyline:+d})")
    print(f"{sim.team_b} win probability: {sim.team_b_win_prob:.1%}  (moneyline {sim.team_b_moneyline:+d})")
    print(f"\nProjected score: {sim.team_a} {sim.team_a_projected_score:.1f} - {sim.team_b} {sim.team_b_projected_score:.1f}")
    print(f"Projected spread: {sim.team_a} {sim.projected_spread:+.1f}")
    print(f"Projected total (over/under): {sim.projected_total:.1f}")

    print("\nModel inputs:")
    _print_rating(report.rating_a)
    _print_rating(report.rating_b)

    print("\n" + "=" * 70)
    print("4. SUMMARY")
    print("=" * 70)
    v = report.verdict
    print(f"\n{v.headline}")
    if v.factors:
        print("\nBiggest factors:")
        for f in v.factors:
            print(f"  - {f}")
    if v.confidence_notes:
        print("\nConfidence notes:")
        for note in v.confidence_notes:
            print(f"  ! {note}")


def _print_recent_form(form: TeamRecentForm) -> None:
    print(f"{form.team}: {form.wins}-{form.losses} over {form.games_played} games")
    if form.points_for_per_game is not None:
        print(f"  Points: {form.points_for_per_game:.1f} for, {form.points_against_per_game:.1f} against")
    print(f"  Home: {form.home_record[0]}-{form.home_record[1]}   Away: {form.away_record[0]}-{form.away_record[1]}")
    if form.strength_of_schedule is not None:
        print(f"  Strength of schedule (avg opponent margin): {form.strength_of_schedule:+.1f}")


def _print_rating(rating) -> None:
    print(f"  {rating.team}: rating {rating.rating:+.1f}, expected points {rating.expected_points:.1f}")
    for key, value in rating.components.items():
        print(f"    {key}: {value:+.1f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfb-matchup", description="Head-to-head history, recent form, and a simulated prediction."
    )
    parser.add_argument("team_a", help='First team, e.g. "Ohio State"')
    parser.add_argument("team_b", help='Second team, e.g. "Michigan"')
    parser.add_argument("--year", type=int, default=2026, help="Season year (default 2026)")
    parser.add_argument("--home-team", default=None, help="Which team hosts this game (default: neutral)")
    parser.add_argument("--neutral-site", action="store_true", help="Game is at a neutral site")
    parser.add_argument(
        "--note-a", action="append", default=[],
        help="A continuity note for team_a (new coach, transfer losses, etc). Repeatable.",
    )
    parser.add_argument(
        "--note-b", action="append", default=[],
        help="A continuity note for team_b. Repeatable.",
    )
    parser.set_defaults(func=cmd_matchup)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
