"""Read-only, multi-year PRE-2025 research cohort gate (operator only).

Accepts an explicit list of already approved private CSV paths, not archive
directories. Inspects full source files; never trains, exports source rows,
licenses input, unlocks a marked staging source, or posts to note.
No GitHub workflow invokes this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import csv
import hashlib

from .pre2025_training_csv_audit import (
    REQUIRED_ALIASES,
    UnsafeTrainingSource,
    audit_pre2025_training_csv,
)

MAX_SHARDS = 12
MAX_TOTAL_ROWS = 3_000_000


@dataclass(frozen=True)
class ResearchCohortAudit:
    status: str
    source_files: int
    source_rows: int
    min_year: int
    max_year: int
    source_years: tuple[int, ...]
    unique_races: int
    independently_verified_research_rights: bool = False
    approved_for_training_by_this_audit: bool = False
    publication_authorized: bool = False
    protected_2025_2026_holdout_opened: bool = False


def audit_multiyear_pre2025_csvs(
    sources: Sequence[Path],
) -> ResearchCohortAudit:
    """Audit year-partitioned, explicitly named CSV files; fail closed.

    Each source is independently subjected to the existing full-file audit.
    The second full scan detects conflicting/repeated race IDs across files,
    even when every individual file has valid dates. No data is returned.
    Research rights and source-to-race lineage require separate review.
    """
    if (not isinstance(sources, (list, tuple))
            or not 2 <= len(sources) <= MAX_SHARDS
            or any(not isinstance(p, Path) for p in sources)
            or len(set(sources)) != len(sources)):
        raise UnsafeTrainingSource("EXPLICIT_DISTINCT_COHORT_CSVS_REQUIRED")

    years: set[int] = set()
    seen_races: set[str] = set()
    total = 0
    for source in sources:
        audited = audit_pre2025_training_csv(source)
        if audited.min_year != audited.max_year:
            raise UnsafeTrainingSource("COHORT_YEAR_PARTITION_INVALID")
        year = audited.min_year
        if year in years:
            raise UnsafeTrainingSource("COHORT_YEAR_PARTITION_DUPLICATED")
        years.add(year)
        total += audited.checked_rows
        if total > MAX_TOTAL_ROWS:
            raise UnsafeTrainingSource("COHORT_TOTAL_ROW_CAP_EXCEEDED")

        # Strict header/record scans (without writing or logging source data).
        try:
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                _audit_distinct_races(stream, seen_races)
        except UnicodeDecodeError:
            # All input formats are pre-audited; try the same legacy
            # encodings accepted by the source audit.
            for encoding in ("cp932", "euc_jp"):
                try:
                    with source.open("r", encoding=encoding, newline="") as stream:
                        _audit_distinct_races(stream, seen_races)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise UnsafeTrainingSource("COHORT_CSV_ENCODING_UNSUPPORTED") from None
        # Keep the second read bound to the exact original audited bytes.
        # Private source digests stay local; never return them in a report.
        with source.open("rb") as raw:
            digest = hashlib.file_digest(raw, "sha256").hexdigest()
        if digest != audited.sha256:
            raise UnsafeTrainingSource("COHORT_SOURCE_CHANGED_AFTER_FULL_AUDIT")

    return ResearchCohortAudit(
        status="STRUCTURAL_COHORT_ONLY_RIGHTS_AND_TRAINING_PENDING",
        source_files=len(sources),
        source_rows=total,
        min_year=min(years),
        max_year=max(years),
        source_years=tuple(sorted(years)),
        unique_races=len(seen_races),
    )


def _audit_distinct_races(stream, seen: set[str]) -> None:
    reader = csv.reader(stream, strict=True)
    try:
        header = [value.strip().lstrip("\ufeff") for value in next(reader)]
        aliases = REQUIRED_ALIASES["race_id"]
        found = [i for i, name in enumerate(header) if name in aliases]
        if len(found) != 1:
            raise UnsafeTrainingSource("COHORT_RACE_KEY_AMBIGUOUS")
        id_index = found[0]
        current_file_ids = set()
        for row in reader:
            if len(row) != len(header) or not row[id_index].strip():
                raise UnsafeTrainingSource("COHORT_INVALID_RACE_KEY")
            current_file_ids.add(row[id_index].strip())
        if seen.intersection(current_file_ids):
            raise UnsafeTrainingSource("COHORT_CROSS_SHARD_RACE_COLLISION")
        seen.update(current_file_ids)
    except (csv.Error, StopIteration):
        raise UnsafeTrainingSource("COHORT_CSV_INVALID") from None
