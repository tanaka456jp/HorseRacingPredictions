"""Verify existing private pedigree snapshot provenance without recreating it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from horse_racing_predictions.jravan_archive_paths import (
    D_DRIVE_ARCHIVE_ROOT, default_archive_root,
)
from horse_racing_predictions.jravan_archive_provenance import (
    validate_local_pre2025_archive,
)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def verify(root: Path) -> dict:
    provenance = validate_local_pre2025_archive(
        root, required_dataspecs=("BLDN",),
    )
    if provenance.manifest_path.name != "relocated_manifest_v2.json":
        raise RuntimeError("Relocated manifest is not authoritative")
    bldn = provenance.parts[0]
    report_path = root / "pedigree_snapshot_report.json"
    snapshot_path = root / "pedigree_snapshot.csv"
    if not report_path.is_file() or not snapshot_path.is_file():
        raise RuntimeError("Private pedigree snapshot/report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "ready":
        raise RuntimeError("Snapshot report is not ready")
    if report.get("raw_identifiers_uploaded") is not False:
        raise RuntimeError("Snapshot must not permit raw-identifier uploads")
    if "2025-2026" not in str(report.get("protected_holdout", "")):
        raise RuntimeError("Snapshot report does not protect final holdout")
    inputs = report.get("input_files", [])
    if inputs != ["bldn_raw.jsonl"]:
        raise RuntimeError("Snapshot was not built exclusively from BLDN")
    maximum = str(report.get("created_date_max") or "")
    minimum = str(report.get("created_date_min") or "")
    if (
        len(minimum) != 8 or not minimum.isdigit()
        or len(maximum) != 8 or not maximum.isdigit()
        or minimum > maximum or maximum > "20241231"
    ):
        raise RuntimeError("Snapshot report is not provably pre-2025")
    expected = str(report.get("snapshot_sha256") or "").lower()
    actual = sha256(snapshot_path)
    if len(expected) != 64 or expected != actual:
        raise RuntimeError("Pedigree snapshot SHA-256 differs from provenance")
    rows = int(report.get("rows") or 0)
    if rows <= 0:
        raise RuntimeError("Pedigree snapshot report has no rows")
    return {
        "status": "verified",
        "manifest_sha256": sha256(provenance.manifest_path),
        "bldn_sha256": bldn.sha256,
        "bldn_records_written": bldn.records_written,
        "snapshot_sha256": actual,
        "pedigree_rows": rows,
        "sire_coverage": report.get("sire_coverage"),
        "damsire_coverage": report.get("damsire_coverage"),
        "created_date_min": minimum,
        "created_date_max": maximum,
        "bldn_only": True,
        "original_pedigree_report_preserved": True,
        "snapshot_regenerated": False,
        "raw_records_parsed": False,
        "one_shot_evaluation_consumed": False,
        "protected_holdout": "2025-2026 untouched",
    }

def main() -> None:
    root = default_archive_root()
    if root != D_DRIVE_ARCHIVE_ROOT:
        raise RuntimeError("Approved D archive is not selected")
    output = verify(root)
    path = Path("artifacts/jravan_pedigree_provenance_verification.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    main()
