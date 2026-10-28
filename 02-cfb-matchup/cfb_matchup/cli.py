import argparse
import sys
from pathlib import Path

from .analysis import MatchupReport, build_matchup_report
from .backtest import (
    BREAK_EVEN_ATS_RATE,
    BacktestGame,
    ats_accuracy,
    ats_graded_games,
    brier_score,
    mean_abs_spread_error,
    mean_abs_total_error,
    over_under_accuracy,
    over_under_graded_games,
    run_backtest,
    win_accuracy,
)
from .bundle import games_from_bundle, load_bundle_file
from .cfbd_client import (
    QuotaExceededError,
    fetch_fbs_teams,
    fetch_h2h_games,
    fetch_recent_universe,
    fetch_returning_production,
    fetch_season_games,
    fetch_season_lines,
    fetch_sp_rating,
    fetch_team_plays,
)
from .config import load_config
from .h2h import head_to_head_games, historical_over_rate
from .models import Game, TeamRecentForm
from .parlay import DEFAULT_PARLAY_STAKE, combined_probability, leg_edges, parlay_ev, parlay_payout
from .power_rating import plays_per_game
from .ranking import game_edge, rank_games
from .recent_form import team_games
from .simulate import moneyline_ev, moneyline_to_implied_prob
from .tables import format_record_table, format_venue_table
from .team_names import resolve_team_name, suggest_team_names
from .verdict import format_spread_line


def _resolve_vegas_spread(line_a: float | None, line_b: float | None) -> float | None:
    """Converts "the points each team is getting" exactly as a sportsbook
    shows them (favorite negative, e.g. -7.5 / +7.5) into this tool's own
    convention (positive = team_a favored by that many points -- see
    SimulationResult.vegas_spread). Accepts either side alone, or both --
    a real line typed from two different places on a betting site (the
    team_a row and the team_b row) should always be exact opposites, so
    both being given is a free consistency check rather than redundant
    input: a mismatch almost certainly means a typo, and silently picking
    one side would build a report around the wrong number.
    """
    if line_a is not None and line_b is not None:
        if abs(line_a + line_b) > 1.0:
            raise ValueError(
                f"--line-a ({line_a:+.1f}) and --line-b ({line_b:+.1f}) don't look like the same line -- "
                "a real spread is the same number on both teams with opposite signs (e.g. -7.5 and +7.5). "
                "Check what you typed, or just pass one of the two."
            )
        return -line_a
    if line_a is not None:
        return -line_a
    if line_b is not None:
        return line_b
    return None


def _resolve_known_teams(config) -> tuple[list[str], dict[str, list[str]]]:
    if not config.api_key:
        raise ValueError(
            "No CollegeFootballData.com API key found. Set the CFBD_API_KEY "
            'environment variable, or add "api_key" to config.json. '
            "Get a free key at https://collegefootballdata.com/key ."
        )
    print("Resolving team names...", file=sys.stderr)
    return fetch_fbs_teams(config.api_key)


def _build_live_report(
    config,
    known_teams: list[str],
    alternate_names: dict[str, list[str]],
    team_a_in: str,
    team_b_in: str,
    year: int,
    home_team_in: str | None,
    neutral_site: bool,
    vegas_spread: float | None,
    vegas_total: float | None,
    vegas_moneyline_a: int | None,
    vegas_moneyline_b: int | None,
    notes_a: list[str] | None = None,
    notes_b: list[str] | None = None,
) -> tuple[MatchupReport, list[Game], list[int], str, str]:
    """Fetches everything build_matchup_report needs for one game and
    builds it -- the live-data half of cmd_matchup, factored out so
    cmd_slate can run this once per game on a slate without duplicating
    this whole block of fetch calls and risking the two drifting apart.
    `known_teams`/`alternate_names` are fetched once by the caller
    (_resolve_known_teams) and passed in, not re-fetched per game -- the
    full FBS team list doesn't change between games on the same slate.
    """
    team_a = _resolve_team(team_a_in, known_teams, alternate_names)
    team_b = _resolve_team(team_b_in, known_teams, alternate_names)

    min_h2h_year = year - config.h2h_seasons_back
    recent_seasons = list(range(year - config.recent_seasons + 1, year + 1))

    print(f"  Fetching head-to-head history ({min_h2h_year}-{year})...", file=sys.stderr)
    h2h_games = fetch_h2h_games(config.api_key, team_a, team_b, min_year=min_h2h_year, max_year=year)

    print("  Fetching recent-form data for both teams and their opponents...", file=sys.stderr)
    recent_games = fetch_recent_universe(config.api_key, team_a, team_b, recent_seasons)

    sp_a = sp_b = None
    if config.use_sp_plus:
        print("  Fetching SP+ ratings...", file=sys.stderr)
        sp_a = fetch_sp_rating(config.api_key, team_a, year)
        sp_b = fetch_sp_rating(config.api_key, team_b, year)

    plays_a_total = plays_b_total = None
    if config.use_pace_adjustment:
        print("  Fetching pace (plays per game) stats...", file=sys.stderr)
        plays_a_total = fetch_team_plays(config.api_key, team_a, year)
        plays_b_total = fetch_team_plays(config.api_key, team_b, year)

    returning_production_a = returning_production_b = None
    if config.use_returning_production:
        print("  Fetching returning production...", file=sys.stderr)
        returning_production_a = fetch_returning_production(config.api_key, team_a, year)
        returning_production_b = fetch_returning_production(config.api_key, team_b, year)

    home_team = _resolve_team(home_team_in, [team_a, team_b]) if home_team_in else None

    # Plays-per-game needs this season's own game count, which is already
    # sitting in recent_games -- no extra fetch for the denominator.
    games_this_season_a = len(team_games(recent_games, team_a, [year]))
    games_this_season_b = len(team_games(recent_games, team_b, [year]))
    pace_a = plays_per_game(plays_a_total, games_this_season_a)
    pace_b = plays_per_game(plays_b_total, games_this_season_b)

    report = build_matchup_report(
        h2h_games,
        recent_games,
        team_a,
        team_b,
        recent_seasons,
        n_simulations=config.n_simulations,
        home_team=home_team,
        neutral_site=neutral_site,
        sp_rating_a=sp_a,
        sp_rating_b=sp_b,
        notes_a=notes_a,
        notes_b=notes_b,
        vegas_spread=vegas_spread,
        vegas_total=vegas_total,
        plays_per_game_a=pace_a,
        plays_per_game_b=pace_b,
        returning_production_a=returning_production_a,
        returning_production_b=returning_production_b,
        vegas_moneyline_a=vegas_moneyline_a,
        vegas_moneyline_b=vegas_moneyline_b,
    )
    return report, h2h_games, recent_seasons, team_a, team_b


def cmd_matchup(args: argparse.Namespace) -> None:
    config = load_config()
    vegas_spread = _resolve_vegas_spread(args.line_a, args.line_b)
    vegas_total = args.over_under
    vegas_moneyline_a = args.moneyline_a
    vegas_moneyline_b = args.moneyline_b

    if args.data_file:
        # A previously-saved cfbd_client.py fetch, re-run from disk instead
        # of hitting the live API again -- build_matchup_report has no idea
        # which path supplied it.
        bundle = load_bundle_file(Path(args.data_file))
        team_a = bundle["team_a"]
        team_b = bundle["team_b"]
        current_year = bundle["year"]
        recent_seasons = bundle["recent_seasons"]
        h2h_games = games_from_bundle(bundle["h2h_games"])
        recent_games = games_from_bundle(bundle["recent_games"])
        sp_a = bundle.get("sp_rating_a")
        sp_b = bundle.get("sp_rating_b")
        # Not part of any bundle format yet -- read defensively (like
        # sp_rating_a/b above) so a bundle without these simply runs
        # without the tempo adjustment rather than failing to load at all.
        plays_a_total = bundle.get("plays_a")
        plays_b_total = bundle.get("plays_b")
        returning_production_a = bundle.get("returning_production_a")
        returning_production_b = bundle.get("returning_production_b")
        home_team = args.home_team or bundle.get("home_team")
        neutral_site = args.neutral_site or bool(bundle.get("neutral_site"))

        games_this_season_a = len(team_games(recent_games, team_a, [current_year]))
        games_this_season_b = len(team_games(recent_games, team_b, [current_year]))
        pace_a = plays_per_game(plays_a_total, games_this_season_a)
        pace_b = plays_per_game(plays_b_total, games_this_season_b)

        report = build_matchup_report(
            h2h_games,
            recent_games,
            team_a,
            team_b,
            recent_seasons,
            n_simulations=config.n_simulations,
            home_team=home_team,
            neutral_site=neutral_site,
            sp_rating_a=sp_a,
            sp_rating_b=sp_b,
            notes_a=args.note_a,
            notes_b=args.note_b,
            vegas_spread=vegas_spread,
            vegas_total=vegas_total,
            plays_per_game_a=pace_a,
            plays_per_game_b=pace_b,
            returning_production_a=returning_production_a,
            returning_production_b=returning_production_b,
            vegas_moneyline_a=vegas_moneyline_a,
            vegas_moneyline_b=vegas_moneyline_b,
        )
    else:
        if not args.team_a or not args.team_b:
            raise ValueError("team_a and team_b are required unless --data-file is given.")
        known_teams, alternate_names = _resolve_known_teams(config)
        report, h2h_games, recent_seasons, team_a, team_b = _build_live_report(
            config,
            known_teams,
            alternate_names,
            args.team_a,
            args.team_b,
            args.year,
            args.home_team,
            args.neutral_site,
            vegas_spread,
            vegas_total,
            vegas_moneyline_a,
            vegas_moneyline_b,
            notes_a=args.note_a,
            notes_b=args.note_b,
        )

    print_report(report, recent_seasons, h2h_games, team_a, team_b)


def _resolve_team(
    typed_name: str, known_teams: list[str], alternate_names: dict[str, list[str]] | None = None
) -> str:
    """Every comparison downstream (h2h.py, recent_form.py, simulate.py's
    home-field check) is a plain string equality against CFBD's exact
    spelling -- so team_a/team_b/home_team have to become that exact
    spelling here, once, or a merely-differently-cased name silently
    matches nothing anywhere in the report instead of raising.
    """
    resolved = resolve_team_name(typed_name, known_teams, alternate_names)
    if resolved is not None:
        return resolved

    if not known_teams:
        # Couldn't fetch the team list at all (network hiccup, quota) --
        # fall back to whatever was typed rather than blocking the whole
        # report over a name that might have been fine.
        print(f"  (couldn't verify '{typed_name}' against CFBD's team list -- using it as typed)", file=sys.stderr)
        return typed_name

    suggestions = suggest_team_names(typed_name, known_teams)
    hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    raise ValueError(f"'{typed_name}' doesn't match any CollegeFootballData team name.{hint}")


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

    pace_a = report.rating_a.components.get("pace_factor")
    pace_b = report.rating_b.components.get("pace_factor")
    if pace_a is not None or pace_b is not None:
        combined_pace = ((pace_a if pace_a is not None else 1.0) + (pace_b if pace_b is not None else 1.0)) / 2
        print(
            f"Game pace factor: {combined_pace:.2f}  (1.00 = both teams at league-average tempo; "
            "below 1.00 means a slower, lower-scoring game -- already baked into the total above)"
        )

    if sim.team_a_home_edge is not None:
        print(
            f"Home-field edge applied: {sim.team_a} +{sim.team_a_home_edge:.1f} pts hosting / "
            f"{sim.team_b} +{sim.team_b_home_edge:.1f} pts hosting -- whichever one is actually "
            "the host in this game gets their own number, from their own home/away scoring split"
        )

    if sim.vegas_spread is not None:
        print(f"\nActual line: {format_spread_line(sim.team_a, sim.team_b, sim.vegas_spread)}")
        print(f"  {sim.team_a} cover probability: {sim.team_a_cover_prob:.1%}")
        print(f"  {sim.team_b} cover probability: {sim.team_b_cover_prob:.1%}")
    if sim.vegas_total is not None:
        print(f"\nActual over/under: {sim.vegas_total:.1f}")
        print(f"  Over probability:  {sim.over_prob:.1%}")
        print(f"  Under probability: {sim.under_prob:.1%}")

    if sim.vegas_moneyline_a is not None:
        print(f"\nActual moneyline, {sim.team_a}: {sim.vegas_moneyline_a:+d}  "
              f"(implies {moneyline_to_implied_prob(sim.vegas_moneyline_a):.1%} vs. model's {sim.team_a_win_prob:.1%}; "
              f"EV at that price: ${moneyline_ev(sim.team_a_win_prob, sim.vegas_moneyline_a):+.2f} per $100 staked)")
    if sim.vegas_moneyline_b is not None:
        print(f"Actual moneyline, {sim.team_b}: {sim.vegas_moneyline_b:+d}  "
              f"(implies {moneyline_to_implied_prob(sim.vegas_moneyline_b):.1%} vs. model's {sim.team_b_win_prob:.1%}; "
              f"EV at that price: ${moneyline_ev(sim.team_b_win_prob, sim.vegas_moneyline_b):+.2f} per $100 staked)")

    print("\nModel inputs:")
    _print_rating(report.rating_a)
    _print_rating(report.rating_b)

    print("\n" + "=" * 70)
    print("4. SUMMARY")
    print("=" * 70)
    v = report.verdict
    print(f"\n{v.headline}")
    if v.spread_pick:
        print(f"\nAgainst the spread: {v.spread_pick}")
    if v.total_pick:
        print(f"\nTotal: {v.total_pick}")
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


def _parse_game(raw: str) -> dict:
    """One game as "team_a,team_b,home_team,line_a,over_under,moneyline_a,moneyline_b"
    -- a blank between commas skips that field, e.g. a neutral-site game
    with no real total typed in: "Ohio State,Michigan,,-7.5,,,". Only
    team_a and team_b are required; everything else is exactly what
    --line-a/--over-under/--moneyline-a/--moneyline-b mean on `matchup`,
    just packed into one field per game so a whole slate fits on one
    command line (or one Colab input() loop).
    """
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 2:
        raise ValueError(f'--game "{raw}" needs at least "team_a,team_b"')
    parts += [""] * (7 - len(parts))
    team_a, team_b, home_team, line_a, over_under, ml_a, ml_b = parts[:7]
    if not team_a or not team_b:
        raise ValueError(f'--game "{raw}": team_a and team_b are required')
    try:
        return {
            "team_a": team_a,
            "team_b": team_b,
            "home_team": home_team or None,
            "line_a": float(line_a) if line_a else None,
            "over_under": float(over_under) if over_under else None,
            "moneyline_a": int(ml_a) if ml_a else None,
            "moneyline_b": int(ml_b) if ml_b else None,
        }
    except ValueError as e:
        raise ValueError(f'--game "{raw}": line_a/over_under must be decimals, moneyline_a/b whole numbers') from e


def cmd_slate(args: argparse.Namespace) -> None:
    """Runs a full matchup report for every game on the slate -- same
    report `matchup` would print, once per game -- then picks the best
    `--top-n` by `ranking.game_edge`: whichever bet each game's own
    verdict actually recommends, how far its probability clears what that
    bet's real price demands. Every game's full analysis prints first;
    the shortlist at the end is purely an added summary on top of it, not
    a replacement for it -- nothing about any individual game's report is
    hidden or abbreviated to make room for the ranking.
    """
    config = load_config()
    if not args.game:
        raise ValueError("Need at least one --game.")

    games = [_parse_game(raw) for raw in args.game]
    known_teams, alternate_names = _resolve_known_teams(config)

    reports: list[MatchupReport] = []
    for i, g in enumerate(games, start=1):
        print(f"\n--- Game {i}/{len(games)}: {g['team_a']} vs {g['team_b']} ---", file=sys.stderr)
        vegas_spread = _resolve_vegas_spread(g["line_a"], None)
        try:
            report, h2h_games, recent_seasons, team_a, team_b = _build_live_report(
                config, known_teams, alternate_names,
                g["team_a"], g["team_b"], args.year,
                g["home_team"], neutral_site=g["home_team"] is None,
                vegas_spread=vegas_spread, vegas_total=g["over_under"],
                vegas_moneyline_a=g["moneyline_a"], vegas_moneyline_b=g["moneyline_b"],
            )
        except ValueError as e:
            print(f"  (skipping {g['team_a']} vs {g['team_b']}: {e})", file=sys.stderr)
            continue

        print_report(report, recent_seasons, h2h_games, team_a, team_b)
        reports.append(report)

    if not reports:
        print("\nNo games could be analyzed.", file=sys.stderr)
        return

    top_n = min(args.top_n, len(reports))
    best = rank_games(reports, top_n)

    print("\n" + "=" * 70)
    print(f"BEST {top_n} OF {len(reports)}")
    print("=" * 70)
    print(
        "\nRanked by how far each game's own best bet clears what its real price demands -- "
        "not win probability alone, and not comparable across bet types by guesswork."
    )
    for rank, report in enumerate(best, start=1):
        edge = game_edge(report)
        pick = report.verdict.spread_pick or "(no pick -- no spread given, or too close to call with no moneyline to fall back on)"
        print(f"\n#{rank}  {report.h2h.team_a} vs {report.h2h.team_b}  (edge {edge:+.1%})")
        print(f"   {pick}")


def cmd_backtest(args: argparse.Namespace) -> None:
    config = load_config()
    if not config.api_key:
        raise ValueError(
            "No CollegeFootballData.com API key found. Set the CFBD_API_KEY "
            'environment variable, or add "api_key" to config.json. '
            "Get a free key at https://collegefootballdata.com/key ."
        )

    test_season = args.season
    fetch_seasons = list(range(test_season - args.history_seasons, test_season + 1))

    all_games: list[Game] = []
    for year in fetch_seasons:
        print(f"Fetching {year} season...", file=sys.stderr)
        all_games.extend(fetch_season_games(config.api_key, year))

    print(f"Fetching {test_season} betting lines...", file=sys.stderr)
    # Only the season actually being tested needs real lines -- every
    # earlier season is only ever used as prior history for a prediction,
    # never graded against the market itself.
    lines = fetch_season_lines(config.api_key, test_season)

    print(f"Backtesting {test_season} ({len(all_games)} games loaded)...", file=sys.stderr)
    results = run_backtest(
        all_games,
        seasons_to_test=[test_season],
        recent_seasons_span=config.recent_seasons,
        n_simulations=args.n_simulations,
        lines=lines,
    )

    print_backtest_report(results, test_season)


def print_backtest_report(results: list[BacktestGame], season: int) -> None:
    print("=" * 70)
    print(f"BACKTEST -- {season} season, {len(results)} games with enough prior history")
    print("=" * 70)

    if not results:
        print("\nNo games had enough prior history to test.")
        return

    print(f"\nWin accuracy (favored team actually won): {win_accuracy(results):.1%}")
    print(f"Brier score (0=perfect, 0.25=coin flip, 1=worst):  {brier_score(results):.3f}")
    print(f"Mean absolute spread error: {mean_abs_spread_error(results):.1f} points")
    print(f"Mean absolute total error:  {mean_abs_total_error(results):.1f} points")

    ats_graded = ats_graded_games(results)
    ou_graded = over_under_graded_games(results)
    print(
        "\nAgainst the spread (vs. the real closing line, not just who won): "
        f"{ats_accuracy(results):.1%} on {len(ats_graded)} of {len(results)} games with a real line "
        "and a real lean"
    )
    print(f"  Break-even against a standard -110 line: {BREAK_EVEN_ATS_RATE:.1%} -- below that loses money over time")
    print(
        f"Over/under (same basis): {over_under_accuracy(results):.1%} on {len(ou_graded)} of {len(results)} games"
    )
    if len(ats_graded) < len(results) // 2:
        print(
            "  (Most games were skipped here -- either no closing line was found for them, or the "
            "model's own cover probability was too close to 50/50 to call a real lean. See README.)"
        )

    worst_totals = sorted(results, key=lambda r: abs(r.predicted_total - r.actual_total), reverse=True)[:5]
    print("\nBiggest total misses (worth checking for a pattern, e.g. a pace/tempo blind spot):")
    for r in worst_totals:
        print(
            f"  wk{r.week}  {r.team_a} vs {r.team_b}: predicted {r.predicted_total:.1f}, "
            f"actual {r.actual_total:.0f}  (off by {abs(r.predicted_total - r.actual_total):.0f})"
        )

    worst_upsets = sorted(
        (r for r in results if not r.favorite_won),
        key=lambda r: abs(r.predicted_win_prob_a - 0.5),
        reverse=True,
    )[:5]
    if worst_upsets:
        print("\nMost confident wrong calls:")
        for r in worst_upsets:
            favored = r.team_a if r.predicted_win_prob_a >= 0.5 else r.team_b
            prob = max(r.predicted_win_prob_a, 1 - r.predicted_win_prob_a)
            print(f"  wk{r.week}  {r.team_a} vs {r.team_b}: gave {favored} {prob:.0%}, but they lost")


def _parse_leg(raw: str) -> tuple[float, int, str]:
    """`raw` is "PROB,ODDS" or "PROB,ODDS,LABEL" -- PROB is the model's own
    win/cover probability for that bet (run `matchup` first to get it, or
    `matchup --line-a ...` for a spread leg's cover probability), ODDS is
    the real sportsbook American price for that exact bet. LABEL is
    optional and only for the printed report; legs are otherwise
    order-independent.
    """
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) not in (2, 3):
        raise ValueError(f'--leg "{raw}" must be "PROB,ODDS" or "PROB,ODDS,LABEL", e.g. "0.75,-230,Georgia Tech"')
    try:
        prob = float(parts[0])
        odds = int(parts[1])
    except ValueError as e:
        raise ValueError(f'--leg "{raw}": PROB must be a decimal (0.75) and ODDS a whole number (-230)') from e
    if not 0.0 < prob < 1.0:
        raise ValueError(f'--leg "{raw}": PROB must be between 0 and 1 (a probability, not a percentage)')
    label = parts[2] if len(parts) == 3 else f"leg {parts[0]}@{parts[1]}"
    return prob, odds, label


def cmd_parlay(args: argparse.Namespace) -> None:
    """Checks a SPECIFIC combination of legs as one all-or-nothing ticket
    -- not whether each leg looks good on its own, but whether betting
    them together, at this stake, is itself worth it. A real user's
    pattern ("$5 parlay, 5 to 6 of the picks need to hit in 1 bet") showed
    exactly the gap this closes: a straight bet's own edge (see
    simulate.moneyline_ev / the matchup command's spread/total picks) says
    nothing about a parlay's combined odds of cashing, which multiply
    every leg's probability together rather than averaging them -- going
    4 of 5 is a complete loss, the same as going 0 of 5.
    """
    if len(args.leg) < 2:
        raise ValueError("A parlay needs at least 2 legs -- pass --leg at least twice.")

    parsed = [_parse_leg(raw) for raw in args.leg]
    probs = [p for p, _, _ in parsed]
    odds_list = [o for _, o, _ in parsed]
    labels = [label for _, _, label in parsed]
    stake = args.stake

    combined_prob = combined_probability(probs)
    payout = parlay_payout(odds_list, stake)
    ev = parlay_ev(probs, odds_list, stake)

    print("=" * 70)
    print(f"PARLAY -- {len(parsed)} legs, ${stake:.2f} staked")
    print("=" * 70)
    print(f"\nCombined odds of cashing (every leg must hit): {combined_prob:.1%}")
    print(f"Payout if every leg hits: ${payout:.2f} (profit ${payout - stake:.2f})")
    print(f"Expected value at this combination and stake: ${ev:+.2f}")
    if ev < 0:
        print(
            "  This loses money on average at these probabilities, even though some -- maybe most -- "
            "of these legs are individually good bets. More legs always lowers the combined odds of "
            "cashing; only real, individual edge on every leg can make up for that."
        )

    print("\nPer-leg breakdown, weakest edge first:")
    for edge in leg_edges(probs, odds_list):
        label = labels[edge.index]
        flag = "  <- dropping this leg always raises the parlay's own EV" if edge.edge <= 0 else ""
        print(
            f"  {label:30s} model {edge.model_prob:.0%}  market-implied {edge.market_implied_prob:.0%}  "
            f"edge {edge.edge:+.1%}{flag}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfb-matchup", description="Head-to-head history, recent form, and a simulated prediction."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    matchup_parser = subparsers.add_parser("matchup", help="Full report for two teams")
    matchup_parser.add_argument("team_a", nargs="?", default=None, help='First team, e.g. "Ohio State" (from --data-file if omitted)')
    matchup_parser.add_argument("team_b", nargs="?", default=None, help='Second team, e.g. "Michigan" (from --data-file if omitted)')
    matchup_parser.add_argument("--year", type=int, default=2026, help="Season year (default 2026)")
    matchup_parser.add_argument(
        "--data-file", default=None,
        help="A JSON file matching cfbd_client.py's output shape -- skips the live API fetch entirely.",
    )
    matchup_parser.add_argument("--home-team", default=None, help="Which team hosts this game (default: neutral)")
    matchup_parser.add_argument("--neutral-site", action="store_true", help="Game is at a neutral site")
    matchup_parser.add_argument(
        "--note-a", action="append", default=[],
        help="A continuity note for team_a (new coach, transfer losses, etc). Repeatable.",
    )
    matchup_parser.add_argument(
        "--note-b", action="append", default=[],
        help="A continuity note for team_b. Repeatable.",
    )
    matchup_parser.add_argument(
        "--line-a", type=float, default=None,
        help='The points given to team_a on a real sportsbook line, exactly as shown (favorite is negative, '
             'e.g. -7.5). Either --line-a or --line-b alone is enough; both is fine too and is cross-checked.',
    )
    matchup_parser.add_argument(
        "--line-b", type=float, default=None,
        help="The points given to team_b on a real sportsbook line, exactly as shown (e.g. +7.5).",
    )
    matchup_parser.add_argument(
        "--over-under", type=float, default=None,
        help="The real sportsbook over/under total for this game, e.g. 54.5.",
    )
    matchup_parser.add_argument(
        "--moneyline-a", type=int, default=None,
        help='The real sportsbook "to win" price for team_a, American odds exactly as shown '
             "(e.g. -230 for a favorite, +185 for an underdog). Only matters when the spread pick falls "
             "back to a straight-up winner -- see README's 'Betting the right side isn't enough' section.",
    )
    matchup_parser.add_argument(
        "--moneyline-b", type=int, default=None,
        help="The real sportsbook \"to win\" price for team_b, same format as --moneyline-a.",
    )
    matchup_parser.set_defaults(func=cmd_matchup)

    backtest_parser = subparsers.add_parser(
        "backtest", help="Test the model against a whole season of already-completed games"
    )
    backtest_parser.add_argument("--season", type=int, default=2025, help="Season to test (default 2025)")
    backtest_parser.add_argument(
        "--history-seasons", type=int, default=5,
        help="Extra prior seasons to fetch so early-season games still have history to predict from (default 5)",
    )
    backtest_parser.add_argument(
        "--n-simulations", type=int, default=1000,
        help="Simulations per game -- lower than a single report's 10,000 default, since this runs many games (default 1000)",
    )
    backtest_parser.set_defaults(func=cmd_backtest)

    parlay_parser = subparsers.add_parser(
        "parlay", help="Check whether a specific combination of legs is worth betting as one all-or-nothing ticket"
    )
    parlay_parser.add_argument(
        "--leg", action="append", default=[], required=True,
        help='One leg as "PROB,ODDS" or "PROB,ODDS,LABEL" -- PROB is the model\'s own win/cover probability '
             "(from running matchup first), ODDS is the real sportsbook price for that bet. Repeatable, "
             'at least twice, e.g. --leg "0.75,-230,Georgia Tech" --leg "0.65,-110,Ohio State spread".',
    )
    parlay_parser.add_argument(
        "--stake", type=float, default=DEFAULT_PARLAY_STAKE,
        help=f"Dollars staked on the whole ticket (default ${DEFAULT_PARLAY_STAKE:.2f})",
    )
    parlay_parser.set_defaults(func=cmd_parlay)

    slate_parser = subparsers.add_parser(
        "slate", help="Run full reports for several games and pick the best --top-n by edge"
    )
    slate_parser.add_argument(
        "--game", action="append", default=[], required=True,
        help='One game as "team_a,team_b,home_team,line_a,over_under,moneyline_a,moneyline_b" -- blank '
             'fields are skipped, e.g. "Ohio State,Michigan,,-7.5,,," for a neutral-site spread-only game. '
             "Repeatable, one per game on the slate.",
    )
    slate_parser.add_argument("--year", type=int, default=2026, help="Season year (default 2026)")
    slate_parser.add_argument(
        "--top-n", type=int, default=4, help="How many of the games to shortlist as the best bets (default 4)",
    )
    slate_parser.set_defaults(func=cmd_slate)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError, QuotaExceededError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
