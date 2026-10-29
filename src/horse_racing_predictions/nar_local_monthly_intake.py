"""Human-operated LOCAL NAR ZIP intake: no provider requests or data export.

Accepts ONLY an explicitly selected, locally downloaded NAR monthly race ZIP
and user-confirmed personal/private research permission. Reads three
pre-2025 official CSV members in memory, checks ZIP integrity and record
schema, and returns aggregate numbers without returning/saving race contents.
No JRA-VAN/JV-Link, note, bookmaker, GitHub artifact, automatic downloader
or paid service is ever called. This never certifies pre-race feature timing,
full historical coverage, commercial rights, or positive expected value.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from .nar_official_zip_probe import (
    UnsafeNarSource, _CSV_RE, inspect_nar_monthly_zip_structure,
)
from .nar_published_result_normalizer import (
    NarInMemoryResult, normalize_nar_published_results,
)

# A small bounded local trial ZIP is safer than loading an entire giant month
# into RAM. Too-large archives fail with a static error without leaking text.
_MAX_SINGLE_CSV_BYTES = 16_000_000
_MAX_ALL_CSV_BYTES = 40_000_000
_ENCODINGS = ("utf-8-sig", "cp932")


@dataclass(frozen=True)
class NarLocalReadiness:
    status: str
    source_month: str
    parsed_races: int
    parsed_starters: int
    min_year: int
    max_year: int
    consent_source: str = "USER_REPORTED_PERSONAL_PRIVATE_PERMISSION"
    source_rights_verified_by_software: bool = False
    pre_event_snapshot_available: bool = False
    authorized_for_training_by_this_check: bool = False
    ev_demonstrated: bool = False
    note_publication_authorized: bool = False
    network_accessed: bool = False


def _decoded_csv(raw: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            text = raw.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        if "\x00" in text:
            raise UnsafeNarSource("NAR_CSV_TEXT_UNSUPPORTED")
        return text
    raise UnsafeNarSource("NAR_CSV_ENCODING_UNSUPPORTED")


def load_nar_monthly_zip_local(
    archive: Path, *, personal_private_permission_confirmed: bool,
) -> NarInMemoryResult:
    """Load *private in-memory finalized races* for future offline studies.

    No entry attributes, forecasts or future-event snapshots are derived.
    """

    The operator independently obtained NAR's personal private permission.
    This human attestation does not grant automatic bulk-download permission.
    All files remain at their original locations with no modifications.
    """
    if personal_private_permission_confirmed is not True:
        raise UnsafeNarSource("NAR_PERSONAL_RESEARCH_PERMISSION_REQUIRED")
    layout = inspect_nar_monthly_zip_structure(archive)
    try:
        with ZipFile(archive, "r") as zf:
            members = {}
            total = 0
            for info in zf.infolist():
                parsed_name = _CSV_RE.fullmatch(info.filename)
                if parsed_name is None:
                    raise UnsafeNarSource("NAR_UNEXPECTED_CSV_MEMBER")
                kind = parsed_name.group(2).lower()
                if (info.file_size > _MAX_SINGLE_CSV_BYTES
                        or info.file_size < 1):
                    raise UnsafeNarSource("NAR_LOCAL_CSV_BYTE_CAP")
                total += info.file_size
                if total > _MAX_ALL_CSV_BYTES:
                    raise UnsafeNarSource("NAR_LOCAL_TOTAL_BYTE_CAP")
                # A second check after ZIP metadata verification ensures
                # the archive is not silently changed before its CSV read.
                if kind in members:
                    raise UnsafeNarSource("NAR_DUPLICATE_CSV_MEMBER")
                members[kind] = info
            if set(members) != {"racelist", "horselist", "payback"}:
                raise UnsafeNarSource("NAR_REQUIRED_CSVS_MISSING")
            texts = {}
            for kind, info in members.items():
                # zipfile enforces member CRC. No extractall(), no path writes.
                with zf.open(info, "r") as stream:
                    raw = stream.read(_MAX_SINGLE_CSV_BYTES + 1)
                    if len(raw) > _MAX_SINGLE_CSV_BYTES:
                        raise UnsafeNarSource("NAR_LOCAL_CSV_BYTE_CAP")
                if len(raw) != info.file_size:
                    raise UnsafeNarSource("NAR_CSV_MEMBER_LENGTH_MISMATCH")
                texts[kind] = _decoded_csv(raw)
        result: NarInMemoryResult = normalize_nar_published_results(
            texts, month=layout.source_month,
        )
    except (BadZipFile, OSError, EOFError, RuntimeError, UnicodeError):
        raise UnsafeNarSource("NAR_LOCAL_ZIP_CONTENT_INVALID") from None
    return result


def read_nar_monthly_zip_local(
    archive: Path, *, personal_private_permission_confirmed: bool,
) -> NarLocalReadiness:
    """Print-safe aggregate-only report for the operator's local ZIP."""
    result = load_nar_monthly_zip_local(
        archive,
        personal_private_permission_confirmed=personal_private_permission_confirmed,
    )
    return NarLocalReadiness(
        status="NAR_LOCAL_FINAL_RESULTS_VALIDATED_NO_PRE_EVENT_PROOF",
        source_month=result.races[0].race_key[1][:6],
        parsed_races=result.audit.checked_races,
        parsed_starters=result.audit.checked_starters,
        min_year=result.audit.min_year,
        max_year=result.audit.max_year,
    )
