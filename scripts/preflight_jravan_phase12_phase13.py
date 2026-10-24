"""Read-only Phase 12/13 readiness gate: metadata only, never a one-shot evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from horse_racing_predictions.jravan_archive_paths import (
    D_DRIVE_ARCHIVE_ROOT,
    default_archive_root,
)
from horse_racing_predictions.jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def preflight(root: Path) -> dict:
    receipt_path = root / "migration_receipt.json"
    derived_path = root / "relocated_manifest_v2.json"
    if not receipt_path.is_file() or not derived_path.is_file():
        raise RuntimeError("Verified migrated archive and relocated manifest are required.")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest = json.loads(derived_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "verified":
        raise RuntimeError("Migration is not verified")
    if receipt.get("source_deleted_after_verify") is not False:
        raise RuntimeError("Copy-only migration source-preservation condition failed")
    if manifest.get("jvopen_range") != DEFAULT_ARCHIVE_RANGE:
        raise RuntimeError("Manifest is not provider-bounded to pre-2025")
    if manifest.get("raw_redistribution_allowed") is not False:
        raise RuntimeError("Raw provider redistribution is not explicitly prohibited")
    if "2025-2026" not in str(manifest.get("protected_holdout", "")):
        raise RuntimeError("Final independent holdout not protected by manifest")
    if sha256(derived_path) != receipt.get("destination_manifest_sha256"):
        raise RuntimeError("Migrated manifest SHA-256 mismatch")
    local_inventory_path = root / "migration_file_hashes.json"
    if not local_inventory_path.is_file():
        raise RuntimeError("Private per-file checksum inventory missing")
    originals = json.loads(local_inventory_path.read_text(encoding="utf-8"))
    original_map = {entry["relative_path"]: entry for entry in originals}
    for name in ("latest_manifest.json", "latest_manifest_v2.json"):
        original = root / name
        entry = original_map.get(name)
        if entry is None or not original.is_file() or sha256(original) != entry["sha256"]:
            raise RuntimeError("Original copied manifest differs from prior verified hash")

    parts = manifest.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("Manifest parts must be a list")
    by_spec = {part["dataspec"]: part for part in parts if isinstance(part, dict)}
    if len(by_spec) != len(parts):
        raise RuntimeError("Duplicate or malformed dataspec entries")

    def usable(name: str) -> bool:
        part = by_spec.get(name)
        if part is None:
            return False
        stamp = str(part.get("last_file_timestamp", ""))
        if (
            part.get("status") != "success"
            or part.get("research_use_allowed") is not True
            or not (stamp[:4].isdigit() and int(stamp[:4]) <= 2024)
        ):
            return False
        candidate = Path(str(part.get("output_path", "")))
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
        except (ValueError, FileNotFoundError):
            return False
        return candidate.is_file()

    race_ready = usable("RACE")
    bldn_ready = usable("BLDN")
    pedigree = (root / "pedigree_snapshot.csv").is_file()
    phase12_receipt_exists = (root / "phase12_evaluation_receipt.json").exists()
    phase13_receipt_exists = (root / "phase13_evaluation_receipt.json").exists()
    phase12_ready = race_ready and bldn_ready and pedigree and not phase12_receipt_exists
    phase13_ready = race_ready and not phase13_receipt_exists

    return {
        "status": "ready" if phase12_ready and phase13_ready else "blocked_preconditions",
        "migration_verified": True,
        "original_manifests_unchanged": True,
        "manifest_sha256": sha256(derived_path),
        "provider_range_pre2025": True,
        "race_research_eligible": race_ready,
        "bldn_research_eligible": bldn_ready,
        "pedigree_snapshot_present": pedigree,
        "phase12_one_shot_receipt_present": phase12_receipt_exists,
        "phase13_one_shot_receipt_present": phase13_receipt_exists,
        "phase12_ready": phase12_ready,
        "phase13_ready": phase13_ready,
        "phase12_13_evaluation_executed": False,
        "raw_records_parsed": False,
        "protected_holdout": "2025-2026 untouched",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, default=None)
    parser.add_argument("--report-output", type=Path,
                        default=Path("artifacts/jravan_phase12_phase13_preflight.json"))
    args = parser.parse_args()
    root = args.archive_root or default_archive_root()
    if args.archive_root is None and root != D_DRIVE_ARCHIVE_ROOT:
        raise RuntimeError("The approved D-drive archive is not active")
    report = preflight(root)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
