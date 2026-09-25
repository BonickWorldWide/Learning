from dataclasses import dataclass, field


@dataclass
class PlayerWeek:
    """A rostered player and this week's real-life matchup.

    gsis_id is resolved up front by manual_roster.py from the current
    roster lookup. It can be blank (unrecognized name) — report.py falls
    back to an empty history rather than crashing.
    """

    name: str
    position: str
    lineup_slot: str
    pro_team: str
    pro_opponent: str
    gsis_id: str | None = None

    @property
    def is_bench(self) -> bool:
        return self.lineup_slot == "BE"


@dataclass
class PlayerMatchupHistory:
    player_name: str
    position: str
    opponent: str
    games_vs_opponent: int
    career_games: int
    ppg_vs_opponent: float | None
    career_ppg: float | None
    ppg_delta: float | None
    stat_averages_vs_opponent: dict[str, float] = field(default_factory=dict)
    stat_averages_career: dict[str, float] = field(default_factory=dict)

    @property
    def small_sample(self) -> bool:
        return self.games_vs_opponent < 3

    @property
    def has_history(self) -> bool:
        return self.games_vs_opponent > 0


@dataclass
class TeamMatchupTendency:
    team: str
    opponent: str
    games: int
    seasons_considered: list[int]
    run_rate: float | None
    pass_rate: float | None
    avg_rush_yards: float | None
    avg_pass_yards: float | None
    avg_points_for: float | None
    position_volume_share: dict[str, float] = field(default_factory=dict)
    top_volume_player: dict[str, str] = field(default_factory=dict)

    @property
    def has_history(self) -> bool:
        return self.games > 0

    @property
    def small_sample(self) -> bool:
        return self.games < 3


@dataclass
class ContinuityFlags:
    team: str
    current_coach: str | None
    prior_coaches: list[str]
    current_qb: str | None
    prior_qbs: list[str]
    notes: list[str] = field(default_factory=list)

    @property
    def head_coach_changed(self) -> bool:
        return bool(self.current_coach) and self.current_coach not in self.prior_coaches and bool(self.prior_coaches)

    @property
    def qb_changed(self) -> bool:
        return bool(self.current_qb) and self.current_qb not in self.prior_qbs and bool(self.prior_qbs)


@dataclass
class PlayerReport:
    player: PlayerWeek
    history: PlayerMatchupHistory
    team_tendency: TeamMatchupTendency
    continuity: ContinuityFlags
