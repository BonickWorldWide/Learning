from dataclasses import dataclass

from .analysis import build_matchup_report
from .models import BettingLine, Game
from .verdict import NO_LEAN_BAND

# Breaking even against a standard -110-on-both-sides sportsbook line
# requires winning 52.4% of the time, not 50% -- the vig means a coin-flip
# picker loses money in the long run. This is the real bar "did this beat
# the market" has to clear, not a bare majority.
BREAK_EVEN_ATS_RATE = 110 / (110 + 100)  # ~0.524


@dataclass
class BacktestGame:
    """One completed game, the model's prediction for it (made using only
    games that happened before it -- no lookahead), and what actually
    happened."""

    season: int
    week: int
    team_a: str
    team_b: str
    predicted_win_prob_a: float
    predicted_spread: float  # team_a's projected score minus team_b's
    predicted_total: float
    actual_score_a: int
    actual_score_b: int
    # The real closing line for this exact game, and the model's own cover
    # probabilities against it -- None unless a matching BettingLine was
    # found for this game (see run_backtest's `lines` argument). Same sign
    # convention as everywhere else in this codebase: positive vegas_spread
    # means team_a (the home team, in backtest's convention) was favored.
    vegas_spread: float | None = None
    vegas_total: float | None = None
    team_a_cover_prob: float | None = None
    over_prob: float | None = None

    @property
    def team_a_won(self) -> bool:
        return self.actual_score_a > self.actual_score_b

    @property
    def actual_margin(self) -> float:
        return self.actual_score_a - self.actual_score_b

    @property
    def actual_total(self) -> float:
        return self.actual_score_a + self.actual_score_b

    @property
    def favorite_won(self) -> bool:
        predicted_a_favored = self.predicted_win_prob_a >= 0.5
        return predicted_a_favored == self.team_a_won

    @property
    def team_a_covered(self) -> bool | None:
        """None (not applicable) when there's no line for this game, or
        it's an exact push -- a push is excluded rather than counted
        either way, the same way a real wager on one would be refunded
        rather than won or lost."""
        if self.vegas_spread is None or self.actual_margin == self.vegas_spread:
            return None
        return self.actual_margin > self.vegas_spread

    @property
    def went_over(self) -> bool | None:
        if self.vegas_total is None or self.actual_total == self.vegas_total:
            return None
        return self.actual_total > self.vegas_total

    @property
    def model_ats_pick(self) -> str | None:
        """Which team the model actually leans against this specific line
        -- None when there's no line, or the model's cover probability is
        too close to 50/50 to call a real lean (same `NO_LEAN_BAND`
        threshold the live report's spread_pick uses, so a game this
        backtest "had no opinion on" is excluded here the same way it
        would be in a real report, not silently coin-flipped into the
        accuracy number).
        """
        if self.team_a_cover_prob is None or abs(self.team_a_cover_prob - 0.5) < NO_LEAN_BAND:
            return None
        return self.team_a if self.team_a_cover_prob > 0.5 else self.team_b

    @property
    def model_total_pick(self) -> str | None:
        if self.over_prob is None or abs(self.over_prob - 0.5) < NO_LEAN_BAND:
            return None
        return "over" if self.over_prob > 0.5 else "under"

    @property
    def ats_pick_won(self) -> bool | None:
        """None when there's nothing to grade: no real pick, or a push."""
        pick, covered = self.model_ats_pick, self.team_a_covered
        if pick is None or covered is None:
            return None
        return covered if pick == self.team_a else not covered

    @property
    def ats_pick_is_underdog(self) -> bool | None:
        """Whether model_ats_pick is the real-money underdog on this
        specific line -- from the actual market spread's sign, not the
        model's own opinion of who's better. A real user noticed the
        model recommends underdogs getting a lot of points unusually
        often; this is what lets ats_accuracy_by_side answer whether
        that's a real, checkable edge or a bias, with real history rather
        than a guess. None when there's no graded pick, or the line is an
        exact pick'em (vegas_spread == 0 -- no real favorite to be the
        underdog against).
        """
        pick = self.model_ats_pick
        if pick is None or self.vegas_spread is None or self.vegas_spread == 0:
            return None
        favored_team = self.team_a if self.vegas_spread > 0 else self.team_b
        return pick != favored_team

    @property
    def total_pick_won(self) -> bool | None:
        pick, over = self.model_total_pick, self.went_over
        if pick is None or over is None:
            return None
        return over if pick == "over" else not over


def _line_lookup(lines: list[BettingLine]) -> dict[tuple, BettingLine]:
    return {(ln.season, ln.week, ln.home_team, ln.away_team): ln for ln in lines}


def run_backtest(
    games: list[Game],
    seasons_to_test: list[int],
    recent_seasons_span: int = 3,
    n_simulations: int = 1000,
    lines: list[BettingLine] | None = None,
) -> list[BacktestGame]:
    """Replays the real model (build_matchup_report, unmodified) against
    every completed game in seasons_to_test, using only games that happened
    strictly before it as that prediction's history.

    A game with no prior history at all (the very first game in the
    dataset) is skipped rather than predicted from nothing.

    `lines` (optional, real closing lines -- see cfbd_client.fetch_season_lines)
    lets every target game be checked against the actual market, not just
    against who won: when a game's line is found, it's passed into
    build_matchup_report exactly the way a live `--line-a`/`--over-under`
    would be, so the *same* simulation tallies real cover/over probabilities
    for free. A game with no matching line (lines not fetched, or CFBD
    simply doesn't have one for it) still gets a normal prediction --
    ats_accuracy/over_under_accuracy (below) just have nothing to grade it
    on.
    """
    targets = sorted(
        (g for g in games if g.season in seasons_to_test),
        key=lambda g: (g.season, g.week),
    )
    line_lookup = _line_lookup(lines or [])

    results = []
    for target in targets:
        historical = [g for g in games if (g.season, g.week) < (target.season, target.week)]
        if not historical:
            continue

        recent_seasons = list(range(target.season - recent_seasons_span + 1, target.season + 1))

        line = line_lookup.get((target.season, target.week, target.home_team, target.away_team))
        # CFBD's spread is relative to the home team, negative when the
        # home team is favored -- the same conversion cli.py does for a
        # typed --line-a. team_a is always the home team in this module's
        # own convention (see BacktestGame docstring).
        vegas_spread = -line.spread if (line and line.spread is not None) else None
        vegas_total = line.over_under if line else None

        report = build_matchup_report(
            h2h_games=historical,
            recent_games=historical,
            team_a=target.home_team,
            team_b=target.away_team,
            recent_seasons=recent_seasons,
            n_simulations=n_simulations,
            home_team=target.home_team,
            neutral_site=target.neutral_site,
            vegas_spread=vegas_spread,
            vegas_total=vegas_total,
        )

        results.append(
            BacktestGame(
                season=target.season,
                week=target.week,
                team_a=target.home_team,
                team_b=target.away_team,
                predicted_win_prob_a=report.simulation.team_a_win_prob,
                predicted_spread=report.simulation.projected_spread,
                predicted_total=report.simulation.projected_total,
                actual_score_a=target.home_score,
                actual_score_b=target.away_score,
                vegas_spread=report.simulation.vegas_spread,
                vegas_total=report.simulation.vegas_total,
                team_a_cover_prob=report.simulation.team_a_cover_prob,
                over_prob=report.simulation.over_prob,
            )
        )
    return results


def brier_score(results: list[BacktestGame]) -> float:
    """0 = perfect, 0.25 = no better than always guessing 50/50, 1 = worst
    possible. The standard way to grade a *probability*, not just a
    right/wrong pick -- a confident wrong call is penalized more than a
    hedged one."""
    if not results:
        return float("nan")
    total = sum((r.predicted_win_prob_a - (1.0 if r.team_a_won else 0.0)) ** 2 for r in results)
    return total / len(results)


def win_accuracy(results: list[BacktestGame]) -> float:
    """Simple hit rate: how often the favored team actually won."""
    if not results:
        return float("nan")
    return sum(1 for r in results if r.favorite_won) / len(results)


def mean_abs_spread_error(results: list[BacktestGame]) -> float:
    if not results:
        return float("nan")
    return sum(abs(r.predicted_spread - r.actual_margin) for r in results) / len(results)


def mean_abs_total_error(results: list[BacktestGame]) -> float:
    if not results:
        return float("nan")
    return sum(abs(r.predicted_total - r.actual_total) for r in results) / len(results)


def ats_graded_games(results: list[BacktestGame]) -> list[BacktestGame]:
    """Only the games this backtest actually had a real spread opinion on
    -- no line found, or the model's own cover probability was too close
    to 50/50 to call a lean (see BacktestGame.model_ats_pick), are
    excluded rather than coin-flipped into the accuracy number. This is
    the real, correct denominator: "how often was the model right when it
    had an opinion," not "how often was the model right including games
    it had nothing to say about."
    """
    return [r for r in results if r.ats_pick_won is not None]


def ats_accuracy(results: list[BacktestGame]) -> float:
    """Fraction of graded picks (see ats_graded_games) that actually
    covered. The real bar this needs to clear to mean anything is
    BREAK_EVEN_ATS_RATE (~52.4%), not 50% -- a standard sportsbook's vig
    means a coin-flip picker loses money over time even at exactly 50%.
    """
    graded = ats_graded_games(results)
    if not graded:
        return float("nan")
    return sum(1 for r in graded if r.ats_pick_won) / len(graded)


@dataclass
class SideAccuracy:
    """One side's slice of ats_accuracy_by_side -- how many picks leaned
    that way, and how many of them actually covered. `n` on its own
    already answers the "does it lean underdog unusually often" question;
    `accuracy` answers whether that lean is actually paying off or not."""

    n: int
    accuracy: float  # NaN when n == 0


def ats_accuracy_by_side(results: list[BacktestGame]) -> dict[str, SideAccuracy]:
    """ats_accuracy, split into the picks that favored the real-money
    underdog vs. the real-money favorite. Both splits producing a similar
    hit rate near or above BREAK_EVEN_ATS_RATE is what a REAL edge on
    underdogs looks like -- a well-documented actual market inefficiency,
    since the betting public tends to overbet favorites and ranked teams,
    and sportsbooks shade lines to account for that bias rather than
    setting a perfectly efficient number. An underdog-pick accuracy well
    above the favorite-pick accuracy, especially combined with a big
    lean toward underdog picks in the first place, instead looks like the
    model itself is miscalibrated on big spreads (its own projected
    margin is systematically smaller than the real line for lopsided
    games) -- both produce "picks underdogs a lot," and only this
    breakdown, run against real history, tells them apart.
    """
    graded = ats_graded_games(results)
    buckets: dict[str, list[bool]] = {"favorite": [], "underdog": []}
    for r in graded:
        is_dog = r.ats_pick_is_underdog
        if is_dog is None:
            continue
        buckets["underdog" if is_dog else "favorite"].append(r.ats_pick_won)

    return {
        side: SideAccuracy(n=len(picks), accuracy=(sum(picks) / len(picks)) if picks else float("nan"))
        for side, picks in buckets.items()
    }


def over_under_graded_games(results: list[BacktestGame]) -> list[BacktestGame]:
    return [r for r in results if r.total_pick_won is not None]


def over_under_accuracy(results: list[BacktestGame]) -> float:
    """Same shape as ats_accuracy, for the total -- graded only on games
    where a real line existed and the model's over probability wasn't
    too close to call."""
    graded = over_under_graded_games(results)
    if not graded:
        return float("nan")
    return sum(1 for r in graded if r.total_pick_won) / len(graded)
