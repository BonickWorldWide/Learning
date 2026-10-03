import random

from .models import SimulationResult

# Points added to whichever team is actually playing at home. 0 for a
# neutral-site game (bowl, conference championship on a neutral field, etc).
HOME_FIELD_ADVANTAGE = 2.5

# Used only when a team doesn't have enough recent games to compute its own
# scoring variance (see recent_form.scoring_std_dev).
DEFAULT_SCORE_STD_DEV = 10.0


def win_prob_to_moneyline(prob: float) -> int:
    """Fair (vig-free) American moneyline odds for a given win probability."""
    prob = min(max(prob, 0.0001), 0.9999)
    if prob >= 0.5:
        return round(-100 * prob / (1 - prob))
    return round(100 * (1 - prob) / prob)


def simulate_game(
    team_a: str,
    team_b: str,
    team_a_expected: float,
    team_b_expected: float,
    team_a_std: float = DEFAULT_SCORE_STD_DEV,
    team_b_std: float = DEFAULT_SCORE_STD_DEV,
    n_simulations: int = 10_000,
    home_team: str | None = None,
    neutral_site: bool = False,
    seed: int | None = None,
    vegas_spread: float | None = None,
    vegas_total: float | None = None,
) -> SimulationResult:
    """Each team's score in each trial is a random draw around its expected
    points (home-field adjusted), std-dev'd by its own real scoring variance.
    A negative draw is clamped to 0 -- an actual score can't be negative.

    `vegas_spread`/`vegas_total` are optional: the actual line from a real
    sportsbook, same sign convention as `projected_spread` (positive means
    team_a is favored by that many points). When given, the *same* trials
    already being drawn for the win probability are also tallied against
    that line -- not a second, separate model -- so "how often does team_a
    beat this specific number" comes from the exact scores the report
    already shows, rather than a closed-form approximation that would need
    its own explanation. A trial landing exactly on the line (a push) is
    counted as not covering/not going over, same simplification as treating
    a tied final score as a loss would be -- rare in practice since lines
    are usually set on a half-point specifically to avoid this.
    """
    rng = random.Random(seed)

    home_bonus_a = HOME_FIELD_ADVANTAGE if (home_team == team_a and not neutral_site) else 0.0
    home_bonus_b = HOME_FIELD_ADVANTAGE if (home_team == team_b and not neutral_site) else 0.0
    mean_a = team_a_expected + home_bonus_a
    mean_b = team_b_expected + home_bonus_b

    a_win_units = 0.0
    a_score_sum = 0.0
    b_score_sum = 0.0
    a_cover_units = 0.0
    over_units = 0.0

    for _ in range(n_simulations):
        score_a = max(0.0, rng.gauss(mean_a, team_a_std))
        score_b = max(0.0, rng.gauss(mean_b, team_b_std))
        a_score_sum += score_a
        b_score_sum += score_b
        if score_a > score_b:
            a_win_units += 1
        elif score_a == score_b:
            a_win_units += 0.5  # a tie counts as half a win for each side's probability
        if vegas_spread is not None and (score_a - score_b) > vegas_spread:
            a_cover_units += 1
        if vegas_total is not None and (score_a + score_b) > vegas_total:
            over_units += 1

    a_win_prob = a_win_units / n_simulations
    b_win_prob = 1 - a_win_prob
    proj_a = a_score_sum / n_simulations
    proj_b = b_score_sum / n_simulations

    a_cover_prob = (a_cover_units / n_simulations) if vegas_spread is not None else None
    b_cover_prob = (1 - a_cover_prob) if a_cover_prob is not None else None
    over_prob = (over_units / n_simulations) if vegas_total is not None else None
    under_prob = (1 - over_prob) if over_prob is not None else None

    return SimulationResult(
        team_a=team_a,
        team_b=team_b,
        n_simulations=n_simulations,
        team_a_win_prob=a_win_prob,
        team_b_win_prob=b_win_prob,
        team_a_projected_score=proj_a,
        team_b_projected_score=proj_b,
        projected_spread=proj_a - proj_b,
        projected_total=proj_a + proj_b,
        team_a_moneyline=win_prob_to_moneyline(a_win_prob),
        team_b_moneyline=win_prob_to_moneyline(b_win_prob),
        vegas_spread=vegas_spread,
        vegas_total=vegas_total,
        team_a_cover_prob=a_cover_prob,
        team_b_cover_prob=b_cover_prob,
        over_prob=over_prob,
        under_prob=under_prob,
    )
