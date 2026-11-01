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
        "monthsStructurallyAccepted": result.months_structurally_accepted,
        "monthsRequiringReview": result.months_with_unresolved_errors,
        "observedRaces": result.observed_races,
        "acceptedFlatRaces": result.accepted_flat_races,
        "predeclaredBaneiOutOfScopeRaces": result.out_of_scope_banei_races,
        "unresolvedFlatRaces": result.unresolved_flat_races,
        "perMonth": [
            {"month": d.month, "status": d.status,
             "observed": d.race_count, "acceptedFlat": d.accepted_flat_races,
             "baneiOutOfScope": d.out_of_scope_banei_races,
             "unresolvedFlat": d.unresolved_flat_races,
             "reasons": dict(d.static_reasons)}
            for d in result.diagnostic
        ],
        "realDataUploaded": False,
        "trainingExecuted": False,
        "actualRoiEvaluated": False,
        "protectedHoldoutOpened": False,
        "publicPostingAuthorized": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result.months_missing == 0 and result.months_with_unresolved_errors == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
