"""Manual, offline NAR training manifest creator (private output only).

The manifest is a JSON array of 72 absolute ZIP paths. This command opens
NO ZIP bytes, downloads no data, accesses no JRA-VAN/COM, fits no model,
publishes nothing, and NEVER writes inside the Git repository.

Default is read-only filename inventory. To write the private path list,
the operator must request --write-private-manifest and supply an absolute
output path OUTSIDE this Git repository, which must not already exist.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.nar_private_manifest_inventory import (
    inventory_private_nar_training_directory,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-nar-training-zip-directory", type=Path,
                        required=True)
    parser.add_argument("--confirm-personal-private-nar-permission",
                        action="store_true")
    parser.add_argument("--write-private-manifest", action="store_true")
    parser.add_argument("--private-manifest-output", type=Path)
    args = parser.parse_args()
    try:
        manifest = inventory_private_nar_training_directory(
            args.local_nar_training_zip_directory,
            personal_private_permission_confirmed=(
                args.confirm_personal_private_nar_permission
            ),
        )
        if args.write_private_manifest:
            output = args.private_manifest_output
            if (output is None or not output.is_absolute()
                    or output.suffix.lower() != ".json"
                    or output.is_symlink()
                    or any(p.is_symlink() for p in output.parents)
                    or not output.parent.is_dir()
                    or output.exists()
                    or output.is_relative_to(Path(__file__).resolve().parents[1])
                    or manifest.missing_months):
                raise UnsafeNarSource("NAR_PRIVATE_MANIFEST_OUTPUT_NOT_SAFE")
            # A private file is intentionally written only after the
            # operator has selected --write-private-manifest.
            with output.open("x", encoding="utf-8") as handle:
                json.dump([str(p) for p in manifest.absolute_source_paths],
                          handle, ensure_ascii=False, indent=2)
        elif args.private_manifest_output is not None:
            raise UnsafeNarSource("NAR_PRIVATE_MANIFEST_WRITE_OPT_IN_REQUIRED")
    except (UnsafeNarSource, OSError, ValueError, TypeError):
        print(json.dumps({
            "status": "NAR_PRIVATE_MANIFEST_BLOCKED",
            "zipContentsOpened": False, "sourceBytesUploaded": False,
            "trainingApproved": False,
        }, sort_keys=True))
        return 2

    print(json.dumps({
        "status": manifest.status,
        "observedMonths": manifest.observed_months,
        "requiredMonths": manifest.required_months,
        "missingMonths": manifest.missing_months,
        "privateManifestWritten": bool(args.write_private_manifest),
        "zipContentsOpened": False, "sourceBytesUploaded": False,
        "trainingApproved": False, "positiveEvDemonstrated": False,
    }, sort_keys=True))
    return 0 if not manifest.missing_months else 3


if __name__ == "__main__":
    raise SystemExit(main())
