"""Operator-supplied local, research-only Friday OOS candidate audit.

This does NOT scan historical archives, download from providers, upload raw
racing data, open a sealed holdout, fit models, post to note or wager. It only
consumes one explicitly named curated *pre-2025* JSON file and returns
aggregate screening results. Self-reported dates and values do not prove
licensing, actual forecast creation times, independent payout provenance or EV.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

from horse_racing_predictions.friday_oos_admission import (
    evaluate_preregistered_friday_oos,
)
from horse_racing_predictions.oddsfree_ev_research import (
    FinalRaceSettlement, FrozenOddsFreeForecast,
)

_SCHEMA = "JRAFridayLockedOOSCandidate.v1"
_INPUT_KEYS = frozenset({
    "schema", "expected_races", "documented_exclusions",
    "forecasts", "settlements",
})
_FORECAST_KEYS = frozenset({
    "race_id", "race_day", "post_time_utc", "predicted_at_utc",
    "model_ref", "model_fit_through_day", "winner_scores",
    "outsider_scores", "odds_used_in_selection",
})
_SETTLEMENT_KEYS = frozenset({
    "race_id", "finishing_positions", "win_return_per_100_yen",
    "place_return_per_100_yen",
})


def _unique_pairs(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError("CANDIDATE_DUPLICATE_JSON_KEY")
        result[key] = val
    return result


def _bad_constant(_value):
    raise ValueError("CANDIDATE_JSON_NONFINITE")


def _read_local_candidate(path: Path):
    if (not path.is_absolute() or path.is_symlink()
            or not path.is_file()
            or path.suffix.lower() != ".json"
            or not 0 < path.stat().st_size <= 20_000_000):
        raise ValueError("CURATED_LOCAL_FILE_REQUIRED")
    raw = path.read_bytes()
    if len(raw) > 20_000_000:
        raise ValueError("CURATED_LOCAL_FILE_TOO_LARGE")
    doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                     parse_constant=_bad_constant)
    if not isinstance(doc, dict) or set(doc) != _INPUT_KEYS or doc["schema"] != _SCHEMA:
        raise ValueError("CANDIDATE_SCHEMA_INVALID")
    if (not isinstance(doc["forecasts"], list)
            or not isinstance(doc["settlements"], list)
            or not isinstance(doc["expected_races"], dict)
            or not isinstance(doc["documented_exclusions"], dict)):
        raise ValueError("CANDIDATE_SEQUENCES_INVALID")
    predictions = []
    for item in doc["forecasts"]:
        if not isinstance(item, dict) or set(item) != _FORECAST_KEYS:
            raise ValueError("CANDIDATE_FORECAST_ENVELOPE_INVALID")
        obj = dict(item)
        obj["post_time_utc"] = datetime.fromisoformat(obj["post_time_utc"])
        obj["predicted_at_utc"] = datetime.fromisoformat(obj["predicted_at_utc"])
        predictions.append(FrozenOddsFreeForecast(**obj))
    results = []
    for item in doc["settlements"]:
        if not isinstance(item, dict) or set(item) != _SETTLEMENT_KEYS:
            raise ValueError("CANDIDATE_SETTLEMENT_ENVELOPE_INVALID")
        results.append(FinalRaceSettlement(**item))
    return doc["expected_races"], predictions, results, doc["documented_exclusions"]


def research_aggregate(path: Path) -> dict:
    expected, forecasts, settlements, excluded = _read_local_candidate(path)
    review = evaluate_preregistered_friday_oos(
        expected_races=expected, forecasts=forecasts,
        settlements=settlements, documented_exclusions=excluded,
    )
    counts = review.admission
    result = {
        "schema": "JRAFridayLockedOOSResearchAggregate.v1",
        "status": review.status,
        "scheduledRaces": counts.scheduled_races,
        "admittedForecasts": counts.frozen_forecasts,
        "matchedSettlements": counts.matched_settlements,
        "excludedRaces": counts.documented_exclusions,
        "exclusionCountsByReason": dict(counts.excluded_by_reason),
        "distinctRaceDays": counts.distinct_racing_dates,
        "minimumSampleSizePassed": counts.meets_preregistered_sample_minimums,
        "economicEvaluationPerformed": review.economic_evaluation_performed,
        "realSourceRightsVerified": False,
        "actualFridayForecastTimingIndependentlyVerified": False,
        "officialPayoutProvenanceIndependentlyVerified": False,
        "positiveExpectedValueDemonstrated": False,
        "protectedHoldoutOpened": False,
        "notePublicationAuthorized": False,
        "liveBettingAuthorized": False,
    }
    if review.economics is not None:
        e = review.economics
        result["diagnosticHistoricalROI"] = {
            "virtualStakeYen": e.combined_stake_yen,
            "virtualReturnYen": e.combined_return_yen,
            "realizedROI": e.combined_realized_roi,
            "dayBlock95Lower": e.combined_bootstrap_95_lower_roi,
            "dayBlock95Upper": e.combined_bootstrap_95_upper_roi,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json", type=Path, required=True)
    parser.add_argument("--local-review-only", action="store_true", required=True)
    args = parser.parse_args()
    try:
        report = research_aggregate(args.candidate_json)
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            UnicodeError, OverflowError) as _exc:
        # Never echo source rows, confidential path, horse names, or raw
        # details from errors in licensed privately prepared data.
        print(json.dumps({"status":"BLOCKED",
              "reason":"LOCAL_CURATED_SOURCE_OR_CHRONOLOGY_REJECTED",
              "positiveExpectedValueDemonstrated":False,
              "notePublicationAuthorized":False}))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if report["economicEvaluationPerformed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
