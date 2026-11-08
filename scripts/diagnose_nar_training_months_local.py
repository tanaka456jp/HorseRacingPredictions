"""Manual offline NAR historical training preflight, no model fitting.

Only selected *local*, user-permitted NAR 2017–2022 monthly ZIP files may
be opened. This CLI does not search the web, download, send data to GitHub,
open 2023–2024 holdout contents, evaluate payoff ROI, or publish forecasts.
Outputs static error codes and per-month aggregate counts ONLY.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.nar_training_preflight import (
    diagnose_nar_training_folder,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_historical_anomaly_triage import (
    triage_historical_nar_anomalies,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-nar-training-zip-directory", type=Path, required=True)
    parser.add_argument("--confirm-personal-private-nar-permission", action="store_true")
    args = parser.parse_args()
    try:
        result = diagnose_nar_training_folder(
            args.local_nar_training_zip_directory,
            personal_private_permission_confirmed=(
                args.confirm_personal_private_nar_permission
            ),
        )
        # Only the complete original training period is eligible for
        # aggregated root-cause triage; never select a profitable subset.
        triage = (triage_historical_nar_anomalies(result)
                  if result.months_present == 72 and result.months_missing == 0
                  else None)
    except (UnsafeNarSource, OSError, ValueError, RuntimeError, TypeError):
        print(json.dumps({
            "status": "NAR_DIAGNOSTIC_BLOCKED_UNTRUSTED_FOLDER_OR_PERMISSION",
            "realDataUploaded": False, "trainingExecuted": False,
            "protectedHoldoutOpened": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result.status,
        "monthsPresent": result.months_present,
        "monthsMissing": result.months_missing,
        "missingMonthIds": result.missing_month_ids,
        "monthsStructurallyAccepted": result.months_structurally_accepted,
        "monthsRequiringReview": result.months_with_unresolved_errors,
        "observedRaces": result.observed_races,
        "acceptedFlatRaces": result.accepted_flat_races,
        "predeclaredBaneiOutOfScopeRaces": result.out_of_scope_banei_races,
        "unresolvedFlatRaces": result.unresolved_flat_races,
        "statusAwareValidatedFlatRaces": result.status_aware_validated_flat_races,
        "statusAwareUnresolvedFlatRaces": result.status_aware_unresolved_flat_races,
        "monthsStatusAwareComplete": result.months_status_aware_complete,
        "unrecognizedMarkerProfiles": dict(result.unrecognized_marker_profile_counts),
        "anomalyTriage": ({
            "schema": "NAR.HistoricalAnomalyTriage.v1",
            "status": triage.status,
            "fullPeriodFlatRaceDenominator": triage.flat_races,
            "strictUnresolvedFlat": triage.strict_unresolved_flat,
            "statusAwareUnresolvedFlat": triage.status_aware_unresolved_flat,
            "newlyInterpretedFlat": triage.newly_interpreted_flat,
            "byYear": [
                {
                    "year": y.year, "months": y.source_months,
                    "flat": y.total_flat_races,
                    "strictUnresolved": y.strict_unresolved_flat,
                    "statusUnresolved": y.status_aware_unresolved_flat,
                    "statusReconciled": y.status_aware_reconciled_flat,
                    "statusCompleteMonths": y.status_complete_months,
                } for y in triage.by_year
            ],
            "byReason": dict(triage.by_reason),
            "byCategory": dict(triage.by_category),
            "ambiguousFinishShapes": dict(triage.ambiguous_finish_shapes),
            "sourceRecordsExported": False,
            "individualRaceIdsExported": False,
            "trainingRowsReleased": 0,
            "positiveEvDemonstrated": False,
        } if triage is not None else None),
        "perMonth": [
            {"month": d.month, "status": d.status,
             "observed": d.race_count, "acceptedFlat": d.accepted_flat_races,
             "baneiOutOfScope": d.out_of_scope_banei_races,
             "unresolvedFlat": d.unresolved_flat_races,
             "reasons": dict(d.static_reasons),
             "statusAwareValidatedFlat": d.status_aware_validated_flat_races,
             "statusAwareUnresolvedFlat": d.status_aware_unresolved_flat_races,
             "statusAwareReasons": dict(d.status_aware_reasons)}
            for d in result.diagnostic
        ],
        "realDataUploaded": False,
        "trainingExecuted": False,
        "actualRoiEvaluated": False,
        "statusAwareAnalysisIsPostEventOnly": True,
        "modelTrainingAuthorized": False,
        "positiveEvDemonstrated": False,
        "protectedHoldoutOpened": False,
        "publicPostingAuthorized": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result.months_missing == 0 and result.months_with_unresolved_errors == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
