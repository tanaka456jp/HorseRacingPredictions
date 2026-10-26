"""Fail-closed, offline PRE-2025 training CSV inspection (stdlib only).

Scan the WHOLE proposed CSV before pandas loads any training records. A
256-KiB sample or a directory named "pre2025" cannot prove its chronology.
No filename, row contents, horse identity or race date is included in
exceptions. Does not independently authorize licence, public posting, or EV.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import csv
import hashlib
from pathlib import Path
import re

CUTOFF = date(2024, 12, 31)
MAX_BYTES = 400_000_000
MAX_ROWS = 3_000_000
REQUIRED_ALIASES = {
    "race_id": ("race_id", "レースID", "Race ID"),
    "race_date": ("race_date", "レース日付", "Race Day"),
    "horse_name": ("horse_name", "馬名", "Horse Name"),
    "finish_position": ("finish_position", "着順", "FP"),
}
_ENCODINGS = ("utf-8-sig", "cp932", "euc_jp")


@dataclass(frozen=True)
class TrainingCsvAudit:
    status: str
    checked_rows: int
    min_year: int
    max_year: int
    sha256: str
    all_source_dates_pre2025: bool = True
    public_redistribution_authorized: bool = False
    independently_licensed_research_authorized: bool = False
    source_training_approved_by_this_audit: bool = False
    protected_holdout_used_as_training: bool = False


class UnsafeTrainingSource(ValueError):
    """Static message only: never echo a sensitive CSV cell or local path."""


def _date_cell(value: str) -> date:
    if not isinstance(value, str):
        raise UnsafeTrainingSource("INVALID_SOURCE_DATE")
    s = value.strip().replace("/", "-")
    if not s or len(s) > 40:
        raise UnsafeTrainingSource("INVALID_SOURCE_DATE")
    # Never accept a loosely matched year prefix such as "2024badrow".
    try:
        d = datetime.fromisoformat(s).date()
    except ValueError:
        try:
            d = date.fromisoformat(s)
        except ValueError as exc:
            raise UnsafeTrainingSource("INVALID_SOURCE_DATE") from exc
    if d < date(1980, 1, 1):
        raise UnsafeTrainingSource("INVALID_SOURCE_DATE")
    return d


def _scan_csv(path: Path, encoding: str) -> tuple[int, int, int]:
    with path.open("r", encoding=encoding, newline="", errors="strict") as handle:
        try:
            reader = csv.reader(handle, strict=True)
            header = next(reader)
        except (csv.Error, StopIteration) as exc:
            raise UnsafeTrainingSource("CSV_HEADER_NOT_READABLE") from exc
        header = [h.strip().lstrip("\ufeff") for h in header]
        if (not header or len(header) > 200
                or any(not h for h in header)
                or len(set(header)) != len(header)):
            raise UnsafeTrainingSource("DUPLICATE_OR_INVALID_SOURCE_HEADER")
        indexes = {}
        for field, aliases in REQUIRED_ALIASES.items():
            matches = [i for i, h in enumerate(header) if h in aliases]
            if len(matches) != 1:
                raise UnsafeTrainingSource("CSV_REQUIRED_SCHEMA_MISSING_OR_AMBIGUOUS")
            indexes[field] = matches[0]
        n = 0
        min_year, max_year = 9999, 0
        try:
            for row in reader:
                n += 1
                if n > MAX_ROWS:
                    raise UnsafeTrainingSource("SOURCE_ROW_LIMIT_EXCEEDED")
                if len(row) != len(header):
                    raise UnsafeTrainingSource("MALFORMED_SOURCE_ROW")
                day = _date_cell(row[indexes["race_date"]])
                # Reject the FIRST protected 2025-26 row even if it lies
                # outside the requested train_start/train_end.
                if day > CUTOFF:
                    raise UnsafeTrainingSource("PROTECTED_HOLDOUT_IN_SOURCE")
                if (not row[indexes["race_id"]].strip()
                        or not row[indexes["horse_name"]].strip()):
                    raise UnsafeTrainingSource("SOURCE_IDENTITY_MISSING")
                min_year = min(min_year, day.year)
                max_year = max(max_year, day.year)
        except csv.Error as exc:
            raise UnsafeTrainingSource("MALFORMED_SOURCE_ROW") from exc
        if n == 0:
            raise UnsafeTrainingSource("EMPTY_SOURCE_CSV")
        return n, min_year, max_year


def audit_pre2025_training_csv(path: Path) -> TrainingCsvAudit:
    """Review date/schema of every row, hash whole file, never train.

    Successful result is structural evidence ONLY, not permission from
    JRA-VAN, netkeiba, Kaggle, or another rightsholder.
    """
    if not isinstance(path, Path) or not path.is_absolute():
        raise UnsafeTrainingSource("ABSOLUTE_LOCAL_SOURCE_REQUIRED")
    if (path.is_symlink() or path.parent.is_symlink()
            or not path.is_file() or path.suffix.lower() != ".csv"):
        raise UnsafeTrainingSource("UNTRUSTED_SOURCE_PATH")
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise UnsafeTrainingSource("UNSAFE_SOURCE_BYTE_SIZE")
    result = None
    for encoding in _ENCODINGS:
        try:
            result = _scan_csv(path, encoding)
            break
        except UnicodeDecodeError:
            continue
    if result is None:
        raise UnsafeTrainingSource("SOURCE_CSV_ENCODING_UNSUPPORTED")
    # A stable local digest helps notice later accidental substitutions.
    # Never print the source filename or file bytes.
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if path.stat().st_size != size:
        raise UnsafeTrainingSource("SOURCE_CHANGED_DURING_INSPECTION")
    rows, first_year, last_year = result
    return TrainingCsvAudit(
        status="FULL_SOURCE_CHRONOLOGY_VERIFIED_PRIVATE_RIGHTS_PENDING",
        checked_rows=rows, min_year=first_year, max_year=last_year,
        sha256=digest,
    )
