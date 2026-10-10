from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from horse_racing_predictions.jravan_free_trial_archive import (
    DEFAULT_ARCHIVE_RANGE,
    FREE_TRIAL_ARCHIVE_DATASPECS,
    archive_free_trial_pre2025,
)


def default_archive_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError(
            "LOCALAPPDATA is required so raw JRA-VAN data stays outside the repo."
        )
    return (
        Path(local)
        / "HorseRacingPredictions"
        / "JraVanFreeTrialArchive"
        / "pre2025"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Archive provider-bounded pre-2025 JRA-VAN setup data locally "
            "during a confirmed zero-cost trial. Raw data never enters Git."
        )
    )
    parser.add_argument("--archive-root", type=Path, default=None)
    parser.add_argument(
        "--range",
        dest="jvopen_range",
        default=DEFAULT_ARCHIVE_RANGE,
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path(
            "artifacts/jravan_free_trial_archive_manifest.json"
        ),
    )
    parser.add_argument(
        "--dataspecs",
        default=",".join(FREE_TRIAL_ARCHIVE_DATASPECS),
    )
    args = parser.parse_args()

    archive_root = (
        args.archive_root
        if args.archive_root is not None
        else default_archive_root()
    )
    archive_root.mkdir(parents=True, exist_ok=True)

    specs = tuple(
        value.strip().upper()
        for value in args.dataspecs.split(",")
        if value.strip()
    )

    def progress(message: str) -> None:
        print(message, flush=True)

    manifest = archive_free_trial_pre2025(
        archive_dir=archive_root,
        manifest_path=args.manifest_output,
        jvopen_range=args.jvopen_range,
        dataspecs=specs,
        zero_cost_entitlement_confirmed=True,
        personal_research_rights_confirmed=True,
        progress_callback=progress,
    )

    latest = archive_root / "latest_manifest.json"
    latest.write_text(
        json.dumps(
            asdict(manifest),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": manifest.status,
                "total_records_written": manifest.total_records_written,
                "dataspecs": list(manifest.dataspecs),
                "archive_root": str(archive_root),
                "manifest_output": str(args.manifest_output),
                "protected_holdout": manifest.protected_holdout,
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    if manifest.status == "failed":
        raise SystemExit(3)
    if manifest.status == "partial":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
