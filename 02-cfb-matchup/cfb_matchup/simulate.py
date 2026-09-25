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
) -> SimulationResult:
    """Each team's score in each trial is a random draw around its expected
    points (home-field adjusted), std-dev'd by its own real scoring variance.
    A negative draw is clamped to 0 -- an actual score can't be negative.
    """
    rng = random.Random(seed)

    home_bonus_a = HOME_FIELD_ADVANTAGE if (home_team == team_a and not neutral_site) else 0.0
    home_bonus_b = HOME_FIELD_ADVANTAGE if (home_team == team_b and not neutral_site) else 0.0
    mean_a = team_a_expected + home_bonus_a
    mean_b = team_b_expected + home_bonus_b

    a_win_units = 0.0
    a_score_sum = 0.0
    b_score_sum = 0.0

    for _ in range(n_simulations):
        score_a = max(0.0, rng.gauss(mean_a, team_a_std))
        score_b = max(0.0, rng.gauss(mean_b, team_b_std))
        a_score_sum += score_a
        b_score_sum += score_b
        if score_a > score_b:
            a_win_units += 1
        elif score_a == score_b:
            a_win_units += 0.5  # a tie counts as half a win for each side's probability

    a_win_prob = a_win_units / n_simulations
    b_win_prob = 1 - a_win_prob
    proj_a = a_score_sum / n_simulations
    proj_b = b_score_sum / n_simulations

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
    )
