from dataclasses import dataclass
from datetime import datetime
import math

from .domain import HorsePrediction


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True)
class PreRaceOddsSnapshot:
    race_id: str
    horse_id: str
    horse_name: str
    decimal_odds: float
    observed_at: datetime
    scheduled_post_time: datetime
    source: str
    source_reference: str = ""

    def __post_init__(self) -> None:
        if not self.race_id.strip():
            raise ValueError("race_id must not be empty")
        if not self.horse_id.strip():
            raise ValueError("horse_id must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not math.isfinite(self.decimal_odds) or self.decimal_odds <= 1.0:
            raise ValueError("decimal_odds must be finite and greater than 1")
        _require_aware(self.observed_at, "observed_at")
        _require_aware(self.scheduled_post_time, "scheduled_post_time")
        if self.observed_at >= self.scheduled_post_time:
            raise ValueError(
                "odds snapshot must be observed before scheduled post time"
            )


def validate_prediction_evidence(
    prediction: HorsePrediction,
    snapshot: PreRaceOddsSnapshot,
    odds_tolerance: float = 1e-12,
) -> None:
    _require_aware(prediction.predicted_at, "predicted_at")

    if prediction.race_id != snapshot.race_id:
        raise ValueError("prediction and odds snapshot race_id do not match")
    if prediction.horse_id != snapshot.horse_id:
        raise ValueError("prediction and odds snapshot horse_id do not match")
    if prediction.predicted_at < snapshot.observed_at:
        raise ValueError(
            "prediction cannot precede the odds observation it claims to use"
        )
    if prediction.predicted_at >= snapshot.scheduled_post_time:
        raise ValueError("prediction must be frozen before scheduled post time")
    if abs(float(prediction.decimal_odds) - float(snapshot.decimal_odds)) > odds_tolerance:
        raise ValueError(
            "prediction decimal_odds must match the linked odds snapshot"
        )
