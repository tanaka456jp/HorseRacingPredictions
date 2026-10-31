"""Local-only NAR 2017–2024 retrospective research readiness CLI.

Explicitly select already authorized local monthly race ZIPs. Never fetch,
glob, search, install, train, upload or post. Reports aggregate coverage and
the number of source races in frozen temporal folds, not source record data.

A structurally complete 96-month archive does not prove historical pre-off
snapshots, lawful redistribution, economic ROI or positive expected value.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.nar_multiyear_readiness import (
    check_nar_multiyear_local,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-monthly-race-zips", type=Path, nargs="+", required=True,
        help="Explicit local ZIP paths only (no wildcard or directory).",
    )
    parser.add_argument(
        "--confirm-personal-private-nar-permission", action="store_true",
        help="Human acknowledgement of NAR's private research permission.",
    )
    args = parser.parse_args()
    try:
        result = check_nar_multiyear_local(
            args.local_monthly_race_zips,
            personal_private_permission_confirmed=(
                args.confirm_personal_private_nar_permission
            ),
        )
    except (UnsafeNarSource, OSError, ValueError, TypeError, KeyError):
        print(json.dumps({
            "status": "NAR_LOCAL_MULTIMONTH_REVIEW_BLOCKED",
            "trainingApproved": False,
            "positiveEvDemonstrated": False,
            "publicationAuthorized": False,
            "downloadAttempted": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result.status,
        "observedMonths": result.observed_months,
        "requiredMonths": result.required_months,
        "missingMonths": result.missing_months,
        "sourceRaces": result.source_races,
        "reconstructedTargets": result.reconstructed_target_races,
        "reconstructedRunners": result.reconstructed_runner_rows,
        "fit2017to2021Races": result.fit_2017_2021_races,
        "tune2022Races": result.tune_2022_races,
        "unseen2023to2024Races": result.unseen_2023_2024_races,
        "preOffSnapshotsVerified": False,
        "realRoiVerified": False,
        "trainingApproved": False,
        "positiveEvDemonstrated": False,
        "publicationAuthorized": False,
        "downloadAttempted": False,
    }, sort_keys=True))
    return 0 if result.missing_months == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
