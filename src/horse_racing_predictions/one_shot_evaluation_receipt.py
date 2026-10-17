"""Fail-closed local one-shot receipts for preregistered Phase 12/13 research.

The claim is created atomically BEFORE parsing the bounded race archive or
fitting any model. A crashed/failed run still consumes the one-shot; human
review is required to change the preregistered research protocol. Neither
this module nor the evaluator retries an attempted run.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value.lower())
    )


def _atomic_json_create(path: Path, data: dict) -> None:
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(
            "A local one-shot evaluation receipt already exists; "
            "the preregistered one-shot evaluation must not be rerun."
        ) from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def claim_one_shot(
    receipt_path: Path,
    *,
    phase: int,
    race_archive_sha256: str,
    pedigree_snapshot_sha256: str | None = None,
) -> dict:
    """Exclusively claim the one-shot. Existing file ALWAYS blocks.

    Caller must first verify local bounded provenance and any required
    snapshot hash; neither raw records nor results have been read yet.
    """
    if phase not in (12, 13):
        raise ValueError("only preregistered phases 12 and 13 are supported")
    if not _sha256_hex(race_archive_sha256):
        raise ValueError("verified race archive SHA-256 is required")
    if phase == 12 and not _sha256_hex(pedigree_snapshot_sha256):
        raise ValueError("Phase 12 requires verified pedigree SHA-256")
    if phase == 13 and pedigree_snapshot_sha256 is not None:
        raise ValueError("Phase 13 does not use pedigree snapshot")
    if receipt_path.is_symlink():
        raise RuntimeError("one-shot receipt must not be a symlink")

    claim = {
        "status": f"phase{phase}_evaluation_started",
        "phase": phase,
        "claim_id": uuid.uuid4().hex,
        "claimed_at_utc": _utc_now(),
        "git_sha": os.environ.get("GITHUB_SHA", "local"),
        "race_archive_sha256": race_archive_sha256.lower(),
        "protected_holdout": "2025-2026 untouched",
        "rerun_allowed": False,
    }
    if phase == 12:
        claim["pedigree_snapshot_sha256"] = pedigree_snapshot_sha256.lower()
    # os.O_EXCL is the actual multi-process one-shot guard, not exists().
    _atomic_json_create(receipt_path, claim)
    return claim


def finalize_one_shot(
    receipt_path: Path,
    *,
    claim: dict,
    summary_sha256: str,
    passed: bool,
) -> None:
    """Atomically upgrade our own claim after a successful evaluation."""
    if not _sha256_hex(summary_sha256):
        raise ValueError("summary SHA-256 must be valid")
    if receipt_path.is_symlink():
        raise RuntimeError("one-shot receipt must not be a symlink")
    current = json.loads(receipt_path.read_text(encoding="utf-8"))
    phase = claim.get("phase")
    if phase not in (12, 13) or current != claim:
        raise RuntimeError("one-shot receipt ownership or claim state changed")
    output = {
        **claim,
        "status": f"phase{phase}_real_evaluation_consumed",
        "completed_at_utc": _utc_now(),
        "summary_sha256": summary_sha256.lower(),
        (
            "development_pedigree_gate_passed"
            if phase == 12 else "development_conditional_partner_gate_passed"
        ): bool(passed),
    }
    temp = receipt_path.with_name(
        receipt_path.name + ".finalize-" + claim["claim_id"]
    )
    try:
        _atomic_json_create(temp, output)
        # os.replace is atomic on the same volume. If interrupted before it
        # happens the original "started" claim still blocks any new run.
        still_current = json.loads(receipt_path.read_text(encoding="utf-8"))
        if still_current != claim:
            raise RuntimeError("one-shot receipt changed during finalization")
        os.replace(temp, receipt_path)
    finally:
        if temp.exists():
            temp.unlink()
