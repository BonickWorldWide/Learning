from dataclasses import dataclass, field


@dataclass
class PlayerWeek:
    name: str
    position: str
    lineup_slot: str
    eligible_slots: list[str] = field(default_factory=list)
    pro_opponent: str = ""
    projected_points: float = 0.0
    injury_status: str = "ACTIVE"

    @property
    def is_bench(self) -> bool:
        return self.lineup_slot == "BE"
