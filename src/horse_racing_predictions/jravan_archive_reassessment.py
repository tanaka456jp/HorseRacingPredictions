"""Reassess an existing local JRA-VAN archive without reading raw records.

This module is metadata-only. It preserves the original latest_manifest.json and
writes latest_manifest_v2.json with corrected no-data semantics and explicit
research-use quarantine based on provider file timestamps.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE


@dataclass(frozen=True)
class ArchiveReassessmentSummary:
    original_manifest_sha256: str
    reassessed_manifest_sha256: str
    total_records_written: int
    successful_dataspecs: tuple[str, ...]
    no_data_dataspecs: tuple[str, ...]
    quarantined_dataspecs: tuple[str, ...]
    failed_dataspecs: tuple[str, ...]
    research_approved_dataspecs: tuple[str, ...]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _provider_year(last_file_timestamp: object) -> int | None:
    value = str(last_file_timestamp or "").strip()
    if len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _is_jvopen_no_data_error(error: object) -> bool:
    value = str(error or "")
    return (
        "JVOpen failed with return code -1" in value
        or "JVOpen returned no applicable data (-1)" in value
    )


def reassess_local_archive_manifest(
    archive_root: str | Path,
    *,
    source_name: str = "latest_manifest.json",
    output_name: str = "latest_manifest_v2.json",
    report_path: str | Path | None = None,
) -> tuple[dict, ArchiveReassessmentSummary]:
    root = Path(archive_root)
    if root.is_symlink():
        raise RuntimeError("archive root must not be a symlink")
    root = root.resolve(strict=True)

    source = root / source_name
    output = root / output_name
    if source.is_symlink() or output.is_symlink():
        raise RuntimeError("archive manifest paths must not be symlinks")
    source = source.resolve(strict=True)

    raw = source.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("jvopen_range") != DEFAULT_ARCHIVE_RANGE:
        raise RuntimeError(
            "cannot reassess an archive outside the approved provider-bound range"
        )
    if payload.get("raw_redistribution_allowed") is not False:
        raise RuntimeError(
            "archive manifest must explicitly forbid raw redistribution"
        )
    protected = str(payload.get("protected_holdout", ""))
    if "2025-2026" not in protected:
        raise RuntimeError(
            "archive manifest does not preserve the protected final holdout"
        )

    parts = payload.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("archive manifest parts must be a list")

    reassessed = deepcopy(payload)
    reassessed["manifest_version"] = 2
    reassessed["reassessed_from"] = source.name
    reassessed["reassessment_policy"] = (
        "JVOpen -1 => no_data; success with provider last_file_timestamp year "
        "<=2024 => research_use_allowed; all other parts fail closed"
    )

    seen: set[str] = set()
    success: list[str] = []
    no_data: list[str] = []
    quarantined: list[str] = []
    failed: list[str] = []
    approved: list[str] = []

    normalized_parts: list[dict] = []
    for original in parts:
        if not isinstance(original, dict):
            raise RuntimeError("archive manifest contains invalid part")
        part = deepcopy(original)
        dataspec = str(part.get("dataspec", "")).strip().upper()
        if not dataspec:
            raise RuntimeError("archive manifest part has no dataspec")
        if dataspec in seen:
            raise RuntimeError(
                f"archive manifest contains duplicate dataspec {dataspec}"
            )
        seen.add(dataspec)

        status = str(part.get("status", ""))
        error = part.get("error")
        if status == "failed" and _is_jvopen_no_data_error(error):
            part["status"] = "no_data"
            part["original_error"] = error
            part["error"] = None
            part["research_use_allowed"] = False
            part["quarantine_reason"] = (
                "JVOpen returned no applicable data (-1); nothing to research"
            )
            no_data.append(dataspec)
        elif status == "success":
            year = _provider_year(part.get("last_file_timestamp"))
            allowed = bool(year is not None and year <= 2024)
            part["research_use_allowed"] = allowed
            part["quarantine_reason"] = (
                None
                if allowed
                else (
                    "provider last_file_timestamp is not certifiably pre-2025; "
                    "archive is preserved but excluded from research use"
                )
            )
            success.append(dataspec)
            if allowed:
                approved.append(dataspec)
            else:
                quarantined.append(dataspec)
        else:
            part["research_use_allowed"] = False
            part["quarantine_reason"] = (
                "provider acquisition failed or status is not research-eligible"
            )
            failed.append(dataspec)

        normalized_parts.append(part)

    reassessed["parts"] = normalized_parts
    acceptable_count = sum(
        1
        for part in normalized_parts
        if part.get("status") in {"success", "no_data"}
    )
    reassessed["status"] = (
        "complete"
        if acceptable_count == len(normalized_parts)
        else ("partial" if acceptable_count else "failed")
    )
    reassessed["total_records_written"] = sum(
        int(part.get("records_written", 0) or 0)
        for part in normalized_parts
        if part.get("status") == "success"
    )

    encoded = json.dumps(
        reassessed,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    output.write_bytes(encoded)

    summary = ArchiveReassessmentSummary(
        original_manifest_sha256=_sha256_bytes(raw),
        reassessed_manifest_sha256=_sha256_bytes(encoded),
        total_records_written=int(reassessed["total_records_written"]),
        successful_dataspecs=tuple(success),
        no_data_dataspecs=tuple(no_data),
        quarantined_dataspecs=tuple(quarantined),
        failed_dataspecs=tuple(failed),
        research_approved_dataspecs=tuple(approved),
    )

    if report_path is not None:
        report = {
            "status": "reassessed",
            "source_manifest": source.name,
            "output_manifest": output.name,
            "original_manifest_sha256": summary.original_manifest_sha256,
            "reassessed_manifest_sha256": summary.reassessed_manifest_sha256,
            "total_records_written": summary.total_records_written,
            "successful_dataspecs": list(summary.successful_dataspecs),
            "no_data_dataspecs": list(summary.no_data_dataspecs),
            "quarantined_dataspecs": list(summary.quarantined_dataspecs),
            "failed_dataspecs": list(summary.failed_dataspecs),
            "research_approved_dataspecs": list(
                summary.research_approved_dataspecs
            ),
            "protected_holdout": "2025-2026 untouched for research use",
            "raw_records_read_during_reassessment": False,
        }
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return reassessed, summary
