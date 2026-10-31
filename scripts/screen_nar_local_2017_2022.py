"""Manual local-only 2017–2022 NAR CatBoost screener.

You must supply a PRIVATE local JSON list of exactly 72 absolute monthly ZIP
paths (no globbing, URL, auto-download, runner, note or source uploads).
The 2023–24 unseen test period is NOT opened, and no model file is saved.
Only a privacy-safe aggregate of 2022 screening accuracy is printed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.nar_local_screening import (
    screen_nar_local_2017_2022,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-zip-paths-json", type=Path, required=True)
    parser.add_argument("--confirm-personal-private-nar-permission",
                        action="store_true")
    parser.add_argument("--iterations", type=int, default=40)
    args = parser.parse_args()
    try:
        manifest = args.private_zip_paths_json
        if (not manifest.is_absolute() or manifest.is_symlink()
                or any(parent.is_symlink() for parent in manifest.parents)
                or not manifest.is_file()
                or not 2 < manifest.stat().st_size <= 30_000):
            raise UnsafeNarSource("NAR_PRIVATE_MANIFEST_INVALID")
        paths = json.loads(manifest.read_text(encoding="utf-8"))
        if (not isinstance(paths, list) or len(paths) != 72
                or any(not isinstance(p, str) or not p.strip()
                       for p in paths)):
            raise UnsafeNarSource("NAR_EXPLICIT_PATH_LIST_INVALID")
        report = screen_nar_local_2017_2022(
            [Path(p) for p in paths],
            personal_private_permission_confirmed=(
                args.confirm_personal_private_nar_permission
            ),
            iterations=args.iterations,
        )
    except (UnsafeNarSource, OSError, ValueError, TypeError, RuntimeError,
            ImportError, KeyError, UnicodeError):
        print(json.dumps({
            "status": "NAR_LOCAL_SCREENING_BLOCKED_SOURCE_OR_FOLDS",
            "sourceRowsUploaded": False,
            "realPayoutRoiVerified": False,
            "independentHoldoutOpened": False,
            "publicationAuthorized": False,
        }, sort_keys=True))
        return 2

    m = report.metrics
    print(json.dumps({
        "status": report.status,
        "monthsChecked": report.months_checked,
        "trainingRaces": m.training_races,
        "tuningRaces": m.tuning_races,
        "trainingRunners": m.training_runners,
        "tuningRunners": m.tuning_runners,
        "tune2022WinTop1": m.winner_top1_hit_rate_2022,
        "tune2022WinTop3Overlap": m.win_rank_top3_overlap_2022,
        "tune2022IndependentOutsiderPodium": (
            m.independent_outsider_podium_hit_rate_2022
        ),
        "sourceRowsUploaded": False,
        "realPayoutRoiVerified": False,
        "independentHoldoutOpened": False,
        "positiveExpectedValueDemonstrated": False,
        "publicationAuthorized": False,
    }, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
