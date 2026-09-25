from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class HorsePrediction:
    race_id: str
    horse_id: str
    horse_name: str
    predicted_win_probability: float
    decimal_odds: float
    confidence: float
    model_version: str
    predicted_at: datetime
    metadata: dict[str, Any] | None = None

    @property
    def fair_odds(self) -> float:
        p = self.predicted_win_probability
        return float("inf") if p <= 0 else 1.0 / p

    @property
    def expected_return_multiple(self) -> float:
        return self.predicted_win_probability * self.decimal_odds

    @property
    def edge(self) -> float:
        return self.expected_return_multiple - 1.0

    def to_dict(self) -> dict:
        out = asdict(self)
        out["predicted_at"] = self.predicted_at.isoformat()
        return out

@dataclass(frozen=True)
class BetDecision:
    race_id: str
    horse_id: str
    horse_name: str
    bet_type: str
    stake_yen: int
    decimal_odds: float
    expected_return_multiple: float
    edge: float
    reason: str
    model_version: str
