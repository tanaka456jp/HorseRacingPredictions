"""Offline full-file RA/SE chronology verifier for large historical JSONL.

Cannot approve a data licence, train a model, or publish data. Never emits
horse names, race dates, filenames or raw JV-Data. Streaming O(1) RAM.
It does not get invoked by any GitHub runner workflow or touch PC2 archives.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from .jv_fixedwidth_ra_se_preflight import verify_ra_se_fixed_width
from .pre2025_training_csv_audit import UnsafeTrainingSource

MAX_BYTES = 8_000_000_000
MAX_LINE_BYTES = 250_000
MAX_ROWS = 25_000_000
CUTOFF = date(2024, 12, 31)
_BLOCKED_FOLDER_NAMES = {
    "jravan-private-quarantine", "2025-2026-holdout",
    "holdout", "final-evaluation", "protected-holdout",
}


@dataclass(frozen=True)
class HistoricalJsonlAudit:
    status: str
    scanned_records: int
    ra_records: int
    se_records: int
    other_record_types: int
    earliest_ra_se_year: int | None
    latest_ra_se_year: int | None
    sha256: str
    all_ra_se_rows_pre2025: bool = True
    whole_archive_source_rights_verified: bool = False
    trainer_input_csv_created: bool = False
    publication_authorized: bool = False
    protected_holdout_opened_for_training: bool = False
    original_data_mutated: bool = False


def audit_pre2025_ra_se_jsonl(path: Path) -> HistoricalJsonlAudit:
    if not isinstance(path, Path) or not path.is_absolute():
        raise UnsafeTrainingSource("ABSOLUTE_JSONL_SOURCE_REQUIRED")
    if (path.suffix.lower() != ".jsonl"
            or path.is_symlink() or path.parent.is_symlink()
            or not path.is_file()):
        raise UnsafeTrainingSource("UNTRUSTED_JSONL_SOURCE")
    if _BLOCKED_FOLDER_NAMES.intersection({p.name.lower() for p in path.parents}):
        raise UnsafeTrainingSource("PROTECTED_ARCHIVE_SOURCE_FORBIDDEN")
    original_size = path.stat().st_size
    if not 0 < original_size <= MAX_BYTES:
        raise UnsafeTrainingSource("UNSAFE_JSONL_SOURCE_BYTE_SIZE")
    digest = sha256()
    ra = se = others = n = 0
    low_year, high_year = 9999, 0
    with path.open("rb") as handle:
        for raw_line in handle:
            n += 1
            if n > MAX_ROWS:
                raise UnsafeTrainingSource("JSONL_ROW_CAP_EXCEEDED")
            if len(raw_line) > MAX_LINE_BYTES:
                raise UnsafeTrainingSource("JSONL_LINE_TOO_LARGE")
            digest.update(raw_line)
            try:
                payload = json.loads(raw_line.decode("utf-8-sig"))
                if not isinstance(payload, dict):
                    raise ValueError("not object")
                kind = payload.get("record_type")
                if kind not in ("RA", "SE"):
                    others += 1
                    continue
                record = payload.get("text")
                if not isinstance(record, str):
                    raise ValueError("missing fixed-width record")
                check = verify_ra_se_fixed_width(kind, record)
                if not all((
                    check.length_valid, check.header_valid,
                    check.jra_course_code_valid, check.date_shape_valid,
                    check.codepage_roundtrip_valid,
                )):
                    raise ValueError("bad fixed-width")
                raw = record.encode("cp932", errors="strict")
                observed = date(
                    int(raw[11:15]), int(raw[15:17]), int(raw[17:19])
                )
                if observed > CUTOFF:
                    raise UnsafeTrainingSource("PROTECTED_HOLDOUT_IN_JSONL")
                low_year = min(low_year, observed.year)
                high_year = max(high_year, observed.year)
                if kind == "RA":
                    ra += 1
                else:
                    se += 1
            except UnsafeTrainingSource:
                raise
            except (ValueError, UnicodeError, TypeError, OverflowError) as exc:
                # Raw JSON or record information must not leak via errors.
                raise UnsafeTrainingSource("JSONL_RECORD_INVALID_OR_UNVERIFIED") from None
    if n < 1 or ra == 0 or se == 0:
        # A single JSONL shard may contain only one record type; this is
        # not independently a complete historical research dataset.
        raise UnsafeTrainingSource("COMPLETE_RA_SE_SOURCE_NOT_PROVEN")
    if path.stat().st_size != original_size:
        raise UnsafeTrainingSource("JSONL_SOURCE_CHANGED_DURING_AUDIT")
    return HistoricalJsonlAudit(
        status="FULL_RA_SE_CHRONOLOGY_VERIFIED_RESEARCH_RIGHTS_PENDING",
        scanned_records=n, ra_records=ra, se_records=se,
        other_record_types=others,
        earliest_ra_se_year=low_year, latest_ra_se_year=high_year,
        sha256=digest.hexdigest(),
    )
