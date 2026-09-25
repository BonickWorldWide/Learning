from dataclasses import dataclass, field


@dataclass
class Game:
    """One played game, from either team's schedule (not just head-to-head)."""

    season: int
    week: int
    date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    neutral_site: bool = False

    @property
    def winner(self) -> str | None:
        if self.home_score == self.away_score:
            return None
        return self.home_team if self.home_score > self.away_score else self.away_team

    @property
    def combined_points(self) -> int:
        return self.home_score + self.away_score

    def margin_for(self, team: str) -> int:
        """Positive = that team won by this many points."""
        if team == self.home_team:
            return self.home_score - self.away_score
        return self.away_score - self.home_score

    def venue_for(self, team: str) -> str:
        """'home', 'away' or 'neutral' from the given team's perspective."""
        if self.neutral_site:
            return "neutral"
        return "home" if team == self.home_team else "away"

    def opponent_of(self, team: str) -> str:
        return self.away_team if team == self.home_team else self.home_team


@dataclass
class VenueSplit:
    venue: str  # "home", "away", "neutral"
    wins: int
    losses: int
    ties: int
    avg_margin: float | None


@dataclass
class RecordSplit:
    """A win/loss/tie record over some window of meetings ("all-time",
    "last 10", "last 20"), from both teams' perspective at once."""

    label: str
    games: int
    team_a_wins: int
    team_b_wins: int
    ties: int
    avg_margin_team_a: float | None
    avg_margin_team_b: float | None


@dataclass
class HeadToHeadSummary:
    team_a: str
    team_b: str
    all_time: RecordSplit
    last_10: RecordSplit
    last_20: RecordSplit
    team_a_venue_splits: dict[str, VenueSplit] = field(default_factory=dict)
    team_b_venue_splits: dict[str, VenueSplit] = field(default_factory=dict)
    longest_streak_team: str | None = None
    longest_streak_len: int = 0
    current_streak_team: str | None = None
    current_streak_len: int = 0
    avg_combined_points: float | None = None

    @property
    def small_sample(self) -> bool:
        return self.all_time.games < 5

    @property
    def rarely_play(self) -> bool:
        return self.all_time.games < 3


@dataclass
class TeamRecentForm:
    team: str
    seasons: list[int]
    games_played: int
    wins: int
    losses: int
    points_for_per_game: float | None
    points_against_per_game: float | None
    home_record: tuple[int, int]
    away_record: tuple[int, int]
    strength_of_schedule: float | None  # avg opponent point differential


@dataclass
class CommonOpponentResult:
    """How each team did the last time it played some shared opponent.

    Inherently a two-team comparison, so it lives on its own rather than
    nested inside either team's TeamRecentForm.
    """

    opponent: str
    team_a_won: bool
    team_a_score: int
    team_a_opp_score: int
    team_b_won: bool
    team_b_score: int
    team_b_opp_score: int


@dataclass
class ContinuityFlags:
    team: str
    notes: list[str] = field(default_factory=list)

    @property
    def has_flags(self) -> bool:
        return len(self.notes) > 0


@dataclass
class PowerRating:
    team: str
    rating: float
    expected_points: float
    components: dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationResult:
    team_a: str
    team_b: str
    n_simulations: int
    team_a_win_prob: float
    team_b_win_prob: float
    team_a_projected_score: float
    team_b_projected_score: float
    projected_spread: float  # positive means team_a favored by this many points
    projected_total: float
    team_a_moneyline: int
    team_b_moneyline: int
