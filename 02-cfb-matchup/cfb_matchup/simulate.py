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


def moneyline_to_implied_prob(odds: int) -> float:
    """The reverse of win_prob_to_moneyline, but for a REAL sportsbook
    price rather than this model's own fair one -- the probability the
    market is effectively pricing in, vig included. A book's two-sided
    odds always imply combined probabilities a little over 100% (the vig),
    so this is deliberately not "removed" here: it's the actual number a
    bettor is laying money against, and that's the number
    moneyline_ev needs.
    """
    if odds < 0:
        return -odds / (-odds + 100)
    return 100 / (odds + 100)


def moneyline_ev(win_prob: float, odds: int, stake: float = 100.0) -> float:
    """Expected profit, in dollars, from betting `stake` at real sportsbook
    `odds` -- given that the TRUE win probability is `win_prob` (the
    model's own number, not the market's). This is the one calculation a
    "pick the more likely winner" recommendation was missing: being right
    more often than not is not the same as the price being worth paying.
    A -400 favorite that's genuinely a 75% shot to win is still a bad bet
    at that price (implied probability 80%) -- the model agreeing with the
    market on direction says nothing about whether the market's price
    already demands more confidence than the model actually has.

    Positive means the bet is profitable on average over many repeats at
    this true probability; negative means the price is worse than the real
    odds justify, however likely that team is to actually win.
    """
    payout_if_win = stake * (100 / -odds) if odds < 0 else stake * (odds / 100)
    return win_prob * payout_if_win - (1 - win_prob) * stake


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
    team_a_home_edge: float = HOME_FIELD_ADVANTAGE,
    team_b_home_edge: float = HOME_FIELD_ADVANTAGE,
    vegas_moneyline_a: int | None = None,
    vegas_moneyline_b: int | None = None,
) -> SimulationResult:
    """Each team's score in each trial is a random draw around its expected
    points (home-field adjusted), std-dev'd by its own real scoring variance.
    A negative draw is clamped to 0 -- an actual score can't be negative.

    `team_a_home_edge`/`team_b_home_edge` default to the flat league-average
    `HOME_FIELD_ADVANTAGE`, but a caller can pass a team-specific number
    instead (see `recent_form.team_home_field_edge`) -- some programs
    genuinely defend their own field better than others (altitude, crowd,
    how far the visitor had to travel), and a single number for every team
    in FBS was never more than a starting approximation. Only whichever
    team is actually hosting gets its own edge added; 0 for the visitor
    and for a neutral site, same as before.

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

    `vegas_moneyline_a`/`vegas_moneyline_b` are the real "to win" price for
    each team, exactly as a sportsbook shows it -- echoed straight onto the
    result (no simulation math touches them) so verdict.py's fallback
    straight-up pick can weigh the model's win probability against what
    that probability would actually pay, not just who's more likely to
    win. See moneyline_ev's docstring for why that distinction matters.
    """
    rng = random.Random(seed)

    home_bonus_a = team_a_home_edge if (home_team == team_a and not neutral_site) else 0.0
    home_bonus_b = team_b_home_edge if (home_team == team_b and not neutral_site) else 0.0
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
        team_a_home_edge=team_a_home_edge,
        team_b_home_edge=team_b_home_edge,
        team_a_cover_prob=a_cover_prob,
        team_b_cover_prob=b_cover_prob,
        over_prob=over_prob,
        under_prob=under_prob,
        vegas_moneyline_a=vegas_moneyline_a,
        vegas_moneyline_b=vegas_moneyline_b,
    )
