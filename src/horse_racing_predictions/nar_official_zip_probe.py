"""Operator-only, source-neutral inspection of a *locally supplied* NAR ZIP.

This module implements the published May 2026 NAR file naming contract.
It does NOT download data, request a provider URL, read the user's old
JRA-VAN archive, extract source data or approve ML/commercial reuse.
NAR terms and permitted local/private usage must be separately reviewed.

NAR official reference:
https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

_ZIP_RE = re.compile(r"^(20[0-9]{4}|19[0-9]{4})_([0-9]{8,13})_race\.zip$", re.I)
_CSV_RE = re.compile(r"^(20[0-9]{4}|19[0-9]{4})_(racelist|horselist|payback)\.csv$", re.I)
_REQUIRED = frozenset({"racelist", "horselist", "payback"})
_MAX_ZIP_BYTES = 400_000_000
_MAX_TOTAL_UNCOMPRESSED = 2_000_000_000
_MAX_CSV_UNCOMPRESSED = 1_000_000_000
_MAX_MEMBERS = 8


class UnsafeNarSource(ValueError):
    """Static errors only, never source filename/content or race identities."""


@dataclass(frozen=True)
class NarZipStructuralReport:
    status: str
    archive_kind: str
    source_month: str
    csv_files: int
    race_list_present: bool
    entry_list_present: bool
    settlement_present: bool
    total_uncompressed_bytes: int
    local_operator_permission_reviewed: bool = False
    actual_rights_independently_verified: bool = False
    opened_source_csv_contents: bool = False
    historical_pre_event_snapshots_verified: bool = False
    eligible_for_training: bool = False
    eligible_for_real_roi: bool = False
    auto_download_enabled: bool = False
    note_publication_authorized: bool = False


def inspect_nar_monthly_zip_structure(source: Path) -> NarZipStructuralReport:
    """Inspect ZIP directory metadata only, without uncompressing race data.

    The true ZIP member schema and rows are *not* verified by this call.
    The caller must nominate an unrelated, lawfully downloaded NAR monthly
    race ZIP, not a JV-Link file, a URL or a protected JRA study source.
    """
    if not isinstance(source, Path) or not source.is_absolute():
        raise UnsafeNarSource("NAR_ABSOLUTE_LOCAL_ZIP_REQUIRED")
    if (source.is_symlink() or any(p.is_symlink() for p in source.parents)
            or not source.is_file()):
        raise UnsafeNarSource("NAR_UNTRUSTED_ARCHIVE_PATH")
    if any(part.lower() in {
        "jravan-private-quarantine", "jra-van", "holdout",
        "2025-2026-holdout", "final-evaluation",
    } for part in source.parts):
        raise UnsafeNarSource("NAR_UNRELATED_PROTECTED_ARCHIVE_FORBIDDEN")
    # Full path is never included in exceptions or the summary.
    match = _ZIP_RE.fullmatch(source.name)
    if not match:
        raise UnsafeNarSource("NAR_OFFICIAL_MONTHLY_RACE_ZIP_NAME_REQUIRED")
    month = match.group(1)
    y, mo = int(month[:4]), int(month[4:])
    if not (1998 <= y <= 2024 and 1 <= mo <= 12):
        # Preserve the separate locked 2025–26 holdout and avoid
        # training-date post-selection on this first NAR protocol.
        raise UnsafeNarSource("NAR_MONTH_OUTSIDE_PRE2025_RESEARCH_WINDOW")
    if not 0 < source.stat().st_size <= _MAX_ZIP_BYTES:
        raise UnsafeNarSource("NAR_ARCHIVE_BYTE_LIMIT")
    try:
        with ZipFile(source, "r") as zf:
            members = zf.infolist()
            if not 3 <= len(members) <= _MAX_MEMBERS:
                raise UnsafeNarSource("NAR_ARCHIVE_MEMBER_COUNT_INVALID")
            seen: set[str] = set()
            total = 0
            for member in members:
                if (member.is_dir() or member.flag_bits & 1
                        or member.file_size <= 0
                        or member.file_size > _MAX_CSV_UNCOMPRESSED
                        or member.compress_size < 0):
                    raise UnsafeNarSource("NAR_ENCRYPTED_OR_OVERSIZED_MEMBER")
                # Reject nested paths and traversal, even though we never
                # extract. This also forbids hidden/system files.
                if ("/" in member.filename or "\\" in member.filename
                        or member.filename.startswith(".")):
                    raise UnsafeNarSource("NAR_NONFLAT_ARCHIVE_MEMBER")
                parsed = _CSV_RE.fullmatch(member.filename)
                if not parsed or parsed.group(1) != month:
                    raise UnsafeNarSource("NAR_UNEXPECTED_CSV_MEMBER")
                member_kind = parsed.group(2).lower()
                if member_kind in seen:
                    raise UnsafeNarSource("NAR_DUPLICATE_CSV_MEMBER")
                seen.add(member_kind)
                total += member.file_size
                if total > _MAX_TOTAL_UNCOMPRESSED:
                    raise UnsafeNarSource("NAR_ARCHIVE_DECOMPRESSION_LIMIT")
            if seen != _REQUIRED:
                raise UnsafeNarSource("NAR_REQUIRED_CSVS_MISSING")
    except (BadZipFile, OSError, EOFError, RuntimeError):
        raise UnsafeNarSource("NAR_ARCHIVE_UNREADABLE") from None
    return NarZipStructuralReport(
        status="NAR_OFFICIAL_FORMAT_CANDIDATE_RIGHTS_AND_ROWS_UNVERIFIED",
        archive_kind="monthly_race",
        source_month=month,
        csv_files=len(seen),
        race_list_present=True,
        entry_list_present=True,
        settlement_present=True,
        total_uncompressed_bytes=total,
    )
