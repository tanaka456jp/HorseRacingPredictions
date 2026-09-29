from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import StrategyConfig
from .domain import HorsePrediction
from .ledger import Ledger
from .paper_session import PaperTradingSession
from .snapshots import PreRaceOddsSnapshot


REQUIRED_COLUMNS = {
    "race_id",
    "horse_id",
    "horse_name",
    "predicted_win_probability",
    "decimal_odds",
    "confidence",
    "model_version",
    "observed_at",
    "predicted_at",
    "scheduled_post_time",
}


@dataclass(frozen=True)
class PaperCsvCase:
    prediction: HorsePrediction
    snapshot: PreRaceOddsSnapshot


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def load_paper_cases(
    path: str | Path,
    default_source: str = "manual_csv",
) -> list[PaperCsvCase]:
    path = Path(path)
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(
                f"missing paper CSV columns: {sorted(missing)}"
            )

        cases = []
        for row_number, row in enumerate(reader, start=2):
            try:
                source = (
                    row.get("source", "").strip()
                    or default_source
                )
                source_reference = row.get(
                    "source_reference",
                    "",
                ).strip()

                snapshot = PreRaceOddsSnapshot(
                    race_id=row["race_id"].strip(),
                    horse_id=row["horse_id"].strip(),
                    horse_name=row["horse_name"].strip(),
                    decimal_odds=float(row["decimal_odds"]),
                    observed_at=_parse_datetime(
                        row["observed_at"]
                    ),
                    scheduled_post_time=_parse_datetime(
                        row["scheduled_post_time"]
                    ),
                    source=source,
                    source_reference=source_reference,
                )
                prediction = HorsePrediction(
                    race_id=snapshot.race_id,
                    horse_id=snapshot.horse_id,
                    horse_name=snapshot.horse_name,
                    predicted_win_probability=float(
                        row["predicted_win_probability"]
                    ),
                    decimal_odds=float(row["decimal_odds"]),
                    confidence=float(row["confidence"]),
                    model_version=row["model_version"].strip(),
                    predicted_at=_parse_datetime(
                        row["predicted_at"]
                    ),
                )
                cases.append(
                    PaperCsvCase(
                        prediction=prediction,
                        snapshot=snapshot,
                    )
                )
            except Exception as exc:
                raise ValueError(
                    f"invalid paper CSV row {row_number}: {exc}"
                ) from exc

    return sorted(
        cases,
        key=lambda item: item.prediction.predicted_at,
    )


def _json_exposure(exposure: dict) -> dict:
    return {
        "day_limits": exposure["day_limits"],
        "day_stakes": exposure["day_stakes"],
        "race_limits": {
            f"{day}|{race_id}": value
            for (day, race_id), value
            in exposure["race_limits"].items()
        },
        "race_stakes": {
            f"{day}|{race_id}": value
            for (day, race_id), value
            in exposure["race_stakes"].items()
        },
    }


def run_paper_csv(
    input_path: str | Path,
    ledger_path: str | Path,
    bankroll_yen: int,
    config: StrategyConfig | None = None,
) -> dict:
    if bankroll_yen <= 0:
        raise ValueError("bankroll_yen must be positive")

    config = config or StrategyConfig()
    cases = load_paper_cases(input_path)
    ledger = Ledger(ledger_path)
    session = PaperTradingSession(
        ledger,
        config,
    )
    evaluations = []

    try:
        existing_race_keys = ledger.paper_evaluated_race_keys()
        skipped_keys = {
            (
                case.prediction.model_version,
                case.prediction.race_id,
            )
            for case in cases
            if (
                case.prediction.model_version,
                case.prediction.race_id,
            ) in existing_race_keys
        }
        skipped_rows = sum(
            1
            for case in cases
            if (
                case.prediction.model_version,
                case.prediction.race_id,
            ) in existing_race_keys
        )
        cases = [
            case
            for case in cases
            if (
                case.prediction.model_version,
                case.prediction.race_id,
            ) not in existing_race_keys
        ]

        model_versions = {
            case.prediction.model_version
            for case in cases
        }
        case_days = {
            case.snapshot.scheduled_post_time.date().isoformat()
            for case in cases
        }
        existing_day_stakes = {
            day: 0
            for day in case_days
        }
        for exposure in ledger.paper_exposures(model_versions):
            scheduled_post_time = _parse_datetime(
                exposure["scheduled_post_time"]
            )
            day_key = scheduled_post_time.date().isoformat()
            if day_key not in case_days:
                continue
            stake = int(exposure["stake_yen"])
            existing_day_stakes[day_key] += stake
            session.seed_exposure(
                scheduled_post_time=scheduled_post_time,
                race_id=exposure["race_id"],
                stake_yen=stake,
                bankroll_yen=bankroll_yen,
            )

        available_by_day = {
            day: max(
                0,
                int(bankroll_yen)
                - int(existing_day_stakes.get(day, 0)),
            )
            for day in case_days
        }

        for case in cases:
            day_key = (
                case.snapshot.scheduled_post_time.date().isoformat()
            )
            available = available_by_day[day_key]
            evaluation_bankroll = (
                available
                if available > 0
                else int(bankroll_yen)
            )
            result = session.evaluate(
                case.prediction,
                case.snapshot,
                bankroll_yen=evaluation_bankroll,
            )

            stake = int(result.decision.stake_yen)
            if result.receipt.accepted:
                available_by_day[day_key] = max(
                    0,
                    available - stake,
                )

            evaluations.append({
                "race_id": case.prediction.race_id,
                "horse_id": case.prediction.horse_id,
                "horse_name": case.prediction.horse_name,
                "predicted_at": (
                    case.prediction.predicted_at.isoformat()
                ),
                "observed_at": (
                    case.snapshot.observed_at.isoformat()
                ),
                "scheduled_post_time": (
                    case.snapshot.scheduled_post_time.isoformat()
                ),
                "probability": (
                    case.prediction.predicted_win_probability
                ),
                "decimal_odds": case.prediction.decimal_odds,
                "ev": (
                    case.prediction.expected_return_multiple
                ),
                "stake_yen": stake,
                "reason": result.decision.reason,
                "accepted": result.receipt.accepted,
                "prediction_id": result.prediction_id,
                "bet_id": result.bet_id,
                "paper_reference": result.receipt.reference,
            })

        committed = sum(
            row["stake_yen"]
            for row in evaluations
            if row["accepted"]
        )
        remaining = (
            min(available_by_day.values())
            if available_by_day
            else int(bankroll_yen)
        )
        return {
            "mode": "paper_only",
            "starting_bankroll_yen": int(bankroll_yen),
            "committed_stake_yen": int(committed),
            "remaining_uncommitted_bankroll_yen": int(remaining),
            "evaluations": evaluations,
            "skipped_existing_races": int(len(skipped_keys)),
            "skipped_existing_evaluation_rows": int(skipped_rows),
            "exposure": _json_exposure(
                session.exposure_snapshot()
            ),
        }
    finally:
        ledger.close()
