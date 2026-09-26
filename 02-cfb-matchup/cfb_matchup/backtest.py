from dataclasses import dataclass

from .analysis import build_matchup_report
from .models import Game


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


def run_backtest(
    games: list[Game],
    seasons_to_test: list[int],
    recent_seasons_span: int = 3,
    n_simulations: int = 1000,
) -> list[BacktestGame]:
    """Replays the real model (build_matchup_report, unmodified) against
    every completed game in seasons_to_test, using only games that happened
    strictly before it as that prediction's history.

    A game with no prior history at all (the very first game in the
    dataset) is skipped rather than predicted from nothing.
    """
    targets = sorted(
        (g for g in games if g.season in seasons_to_test),
        key=lambda g: (g.season, g.week),
    )

    results = []
    for target in targets:
        historical = [g for g in games if (g.season, g.week) < (target.season, target.week)]
        if not historical:
            continue

        recent_seasons = list(range(target.season - recent_seasons_span + 1, target.season + 1))

        report = build_matchup_report(
            h2h_games=historical,
            recent_games=historical,
            team_a=target.home_team,
            team_b=target.away_team,
            recent_seasons=recent_seasons,
            n_simulations=n_simulations,
            home_team=target.home_team,
            neutral_site=target.neutral_site,
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
