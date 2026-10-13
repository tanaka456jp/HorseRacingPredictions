"""Metadata and SHA-only C-drive archive audit. No provider or history access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from horse_racing_predictions.jravan_archive_paths import legacy_localappdata_archive_root


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(source: Path, *, storage_label: str = "legacy LOCALAPPDATA private archive") -> dict:
    if source.is_symlink():
        raise RuntimeError("Symlink archive root is prohibited")
    root = source.resolve(strict=True)
    paths = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: str(p))
    if not paths or any(p.is_symlink() for p in root.rglob("*")):
        raise RuntimeError("Archive is missing or contains a symlink")
    file_hashes = {}
    inventory_hash = hashlib.sha256()
    total = 0
    for path in paths:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        digest = sha256(path)
        file_hashes[relative] = digest
        total += size
        inventory_hash.update((relative + "\0" + str(size) + "\0" + digest + "\n").encode("utf-8"))

    source_manifest = root / "latest_manifest.json"
    v2_manifest = root / "latest_manifest_v2.json"
    if not source_manifest.is_file():
        candidates = {
            "archive_parent": root.parent / "latest_manifest.json",
            "app_archive_parent": root.parent.parent / "latest_manifest.json",
            "runner_sanitized_artifact": Path.cwd() / "artifacts" / "jravan_free_trial_archive_manifest.json",
            "runner_primary_manifest": Path.cwd() / "artifacts" / "latest_manifest.json",
        }
        return {
            "status": "needs_primary_manifest_recovery",
            "source_storage": storage_label,
            "file_count": len(paths),
            "total_bytes": total,
            "inventory_sha256": inventory_hash.hexdigest(),
            "primary_manifest_present": False,
            "reassessed_manifest_exists": v2_manifest.is_file(),
            "candidate_manifest_locations": {
                label: target.is_file() for label, target in candidates.items()
            },
            "c_drive_data_modified": False,
            "provider_access_attempted": False,
            "protected_holdout": "2025-2026 untouched",
        }
    preferred = v2_manifest if v2_manifest.is_file() else source_manifest
    payload = json.loads(preferred.read_text(encoding="utf-8"))
    if payload.get("raw_redistribution_allowed") is not False:
        raise RuntimeError("Manifest does not prohibit raw redistribution")
    if "2025-2026" not in str(payload.get("protected_holdout", "")):
        raise RuntimeError("Final holdout preservation is not proven")
    parts = payload.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("Malformed manifest parts")
    verified_parts = 0
    quarantined = 0
    for part in parts:
        if not isinstance(part, dict):
            raise RuntimeError("Malformed manifest part")
        if part.get("status") != "success":
            continue
        raw = Path(str(part.get("output_path", "")))
        if not raw.is_absolute():
            raw = root / raw
        raw = raw.resolve(strict=True)
        try:
            relative = raw.relative_to(root).as_posix()
        except ValueError as exc:
            raise RuntimeError("Manifest references an external archive file") from exc
        if file_hashes.get(relative) != str(part.get("output_sha256", "")).lower():
            raise RuntimeError("Manifest-referenced file SHA-256 mismatch")
        verified_parts += 1
        if part.get("research_use_allowed") is not True:
            quarantined += 1
    return {
        "status": "verified_inventory",
        "source_storage": "legacy LOCALAPPDATA private archive",
        "file_count": len(paths),
        "total_bytes": total,
        "inventory_sha256": inventory_hash.hexdigest(),
        "original_manifest_sha256": file_hashes["latest_manifest.json"],
        "reassessed_manifest_exists": v2_manifest.is_file(),
        "reassessed_manifest_sha256": file_hashes.get("latest_manifest_v2.json"),
        "manifest_record_count": int(payload.get("total_records_written", 0) or 0),
        "manifest_success_parts_verified": verified_parts,
        "manifest_success_parts_quarantined": quarantined,
        "c_drive_data_modified": False,
        "provider_access_attempted": False,
        "protected_holdout": "2025-2026 untouched",
    }


def main() -> None:
    legacy = legacy_localappdata_archive_root()
    previous_d = Path(r"D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025")
    if (legacy / "latest_manifest.json").is_file():
        report = audit(legacy)
    else:
        prior_receipt = previous_d / "migration_receipt.json"
        if not (legacy / "MOVED_TO_D.json").is_file() or not prior_receipt.is_file():
            raise RuntimeError("Primary manifest and verified prior D archive both missing.")
        status = json.loads(prior_receipt.read_text(encoding="utf-8"))
        if status.get("status") != "verified":
            raise RuntimeError("Old D archive is not accompanied by verified receipt.")
        report = audit(previous_d, storage_label="previously verified D private archive")
    path = Path("artifacts/jravan_archive_c_inventory_report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "verified_inventory":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
