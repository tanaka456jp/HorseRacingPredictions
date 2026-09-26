from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from .odds_provider import CsvOddsSnapshotProvider


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def prepare_paper_input(
    predictions: pd.DataFrame,
    odds_provider: CsvOddsSnapshotProvider,
    decision_time: datetime,
) -> pd.DataFrame:
    _require_aware(decision_time, "decision_time")

    required = {
        "race_id",
        "horse_id",
        "horse_name",
        "predicted_win_probability",
        "confidence",
        "model_version",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(
            f"missing prediction columns: {sorted(missing)}"
        )

    rows = []
    for race_id, race_predictions in predictions.groupby(
        "race_id",
        sort=False,
    ):
        snapshots = odds_provider.snapshots_for_race(str(race_id))
        eligible = [
            snapshot
            for snapshot in snapshots
            if snapshot.observed_at <= decision_time
            and decision_time < snapshot.scheduled_post_time
        ]

        latest = {}
        for snapshot in eligible:
            current = latest.get(snapshot.horse_id)
            if (
                current is None
                or snapshot.observed_at > current.observed_at
            ):
                latest[snapshot.horse_id] = snapshot

        for prediction in race_predictions.itertuples(index=False):
            horse_id = str(prediction.horse_id)
            snapshot = latest.get(horse_id)
            if snapshot is None:
                raise ValueError(
                    "no eligible pre-race odds snapshot for "
                    f"{race_id}/{horse_id} at {decision_time.isoformat()}"
                )
            if str(prediction.horse_name) != snapshot.horse_name:
                raise ValueError(
                    "prediction and odds snapshot horse_name do not match "
                    f"for {race_id}/{horse_id}"
                )

            rows.append({
                "race_id": str(race_id),
                "horse_id": horse_id,
                "horse_name": snapshot.horse_name,
                "predicted_win_probability": float(
                    prediction.predicted_win_probability
                ),
                "decimal_odds": float(snapshot.decimal_odds),
                "confidence": float(prediction.confidence),
                "model_version": str(prediction.model_version),
                "observed_at": snapshot.observed_at.isoformat(),
                "predicted_at": decision_time.isoformat(),
                "scheduled_post_time": (
                    snapshot.scheduled_post_time.isoformat()
                ),
                "source": snapshot.source,
                "source_reference": snapshot.source_reference,
            })

    if not rows:
        raise ValueError("no Paper Trading input rows were generated")
    return pd.DataFrame(rows)


def prepare_paper_input_files(
    predictions_path: str | Path,
    odds_path: str | Path,
    output_path: str | Path,
    decision_time: datetime | None = None,
) -> Path:
    predictions = pd.read_csv(
        predictions_path,
        encoding="utf-8-sig",
    )
    provider = CsvOddsSnapshotProvider(odds_path)
    decision_time = decision_time or datetime.now(timezone.utc)
    prepared = prepare_paper_input(
        predictions,
        provider,
        decision_time,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(
        output,
        index=False,
        encoding="utf-8-sig",
    )
    return output
