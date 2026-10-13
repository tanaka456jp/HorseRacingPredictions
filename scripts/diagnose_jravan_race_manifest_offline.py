"""Inspect only existing private JRA-VAN manifest metadata; never call JV-Link."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from horse_racing_predictions.jravan_archive_paths import (
    D_DRIVE_ARCHIVE_ROOT,
    default_archive_root,
)
from horse_racing_predictions.jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE

MANIFEST_NAMES = (
    "latest_manifest.json",
    "latest_manifest_v2.json",
    "relocated_manifest_v2.json",
)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _safe_code(error: object) -> str:
    message = str(error or "")
    result = re.search(r"(?:return code|\\()\\s*(-?\\d+)\\b", message)
    if result:
        return str(int(result.group(1)))
    if re.search(r"-301\\b", message):
        return "-301"
    if re.search(r"-1\\b", message):
        return "-1"
    return "not_recorded"

def diagnose(root: Path) -> dict:
    if root.is_symlink():
        raise RuntimeError("Archive root cannot be a symlink")
    root = root.resolve(strict=True)
    manifest_audits = []
    for name in MANIFEST_NAMES:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Required local manifest missing or unsafe: " + name)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("jvopen_range") != DEFAULT_ARCHIVE_RANGE:
            raise RuntimeError("Manifest range is not pre-2025 bounded")
        if payload.get("raw_redistribution_allowed") is not False:
            raise RuntimeError("Manifest does not forbid redistribution")
        if "2025-2026" not in str(payload.get("protected_holdout", "")):
            raise RuntimeError("Final holdout is not preserved")
        parts = payload.get("parts")
        if not isinstance(parts, list):
            raise RuntimeError("Manifest parts are not a list")
        seen = set()
        statuses = []
        for part in parts:
            if not isinstance(part, dict):
                raise RuntimeError("Invalid manifest part")
            name_spec = str(part.get("dataspec", "")).strip().upper()
            if not name_spec or name_spec in seen:
                raise RuntimeError("Missing or duplicated dataspec")
            seen.add(name_spec)
            status = str(part.get("status", ""))
            raw_path = Path(str(part.get("output_path") or ""))
            if not raw_path.is_absolute():
                raw_path = root / raw_path
            try:
                within = raw_path.resolve().is_relative_to(root)
            except (OSError, ValueError):
                within = False
            # Only a filename/size presence test, never open raw bytes.
            present = within and raw_path.is_file()
            dataspec = {
                "dataspec": name_spec,
                "status": status,
                "records_reported": int(part.get("records_written") or 0),
                "research_use_allowed": part.get("research_use_allowed") is True,
                "error_return_code": _safe_code(part.get("error") or part.get("original_error")),
                "raw_file_present": bool(present),
                "has_sha256": bool(re.fullmatch(r"[0-9a-fA-F]{64}",str(part.get("output_sha256") or ""))),
                "provider_last_file_year": str(part.get("last_file_timestamp") or "")[:4]
                    if str(part.get("last_file_timestamp") or "")[:4].isdigit() else None,
            }
            statuses.append(dataspec)
        manifest_audits.append({
            "name": path.name,
            "sha256": _sha256(path),
            "records_reported": int(payload.get("total_records_written") or 0),
            "parts": statuses,
        })

    original = manifest_audits[0]
    derived = manifest_audits[-1]
    statuses = {part["dataspec"]: part for part in derived["parts"]}
    race = statuses.get("RACE")
    if race is None:
        raise RuntimeError("RACE was not recorded in bounded provenance")
    blocking = (
        race["status"] != "success"
        or race["research_use_allowed"] is not True
        or race["raw_file_present"] is not True
        or race["has_sha256"] is not True
        or (race["provider_last_file_year"] is None
            or int(race["provider_last_file_year"]) > 2024)
    )
    return {
        "status": "race_blocked" if blocking else "race_manifest_eligible",
        "manifest_evidence": [
            {k:v for k,v in report.items() if k != "parts"}
            for report in manifest_audits
        ],
        "race_from_original": next(
            (x for x in original["parts"] if x["dataspec"] == "RACE"), None
        ),
        "race_from_reassessed": next(
            (x for x in manifest_audits[1]["parts"] if x["dataspec"] == "RACE"), None
        ),
        "race_from_relocated": race,
        "all_relocated_parts": derived["parts"],
        "other_research_approved_specs": sorted(
            p["dataspec"] for p in derived["parts"]
            if p["research_use_allowed"] and p["status"] == "success"
        ),
        "provider_access_attempted": False,
        "usage_key_read": False,
        "raw_records_read": False,
        "archive_modified": False,
        "phase12_13_one_shot_evaluation_run": False,
        "protected_holdout": "2025-2026 untouched",
        "potential_next_action": (
            "No automatic provider retries or substitute data. "
            "Confirm RACE authentication/zero-cost rights separately."
            if blocking else "Perform independent bounded provenance check before any one-shot."
        ),
    }

def main() -> None:
    root = default_archive_root()
    if root != D_DRIVE_ARCHIVE_ROOT:
        raise RuntimeError("Approved D archive has not been selected")
    report = diagnose(root)
    path = Path("artifacts/jravan_race_manifest_diagnosis.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
