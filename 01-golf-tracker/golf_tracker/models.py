from dataclasses import dataclass, asdict
from datetime import date


@dataclass
class Round:
    course: str
    par: int
    strokes: int
    played_on: date

    @property
    def to_par(self) -> int:
        return self.strokes - self.par

    def to_dict(self) -> dict:
        data = asdict(self)
        data["played_on"] = self.played_on.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Round":
        return cls(
            course=data["course"],
            par=int(data["par"]),
            strokes=int(data["strokes"]),
            played_on=date.fromisoformat(data["played_on"]),
        )
