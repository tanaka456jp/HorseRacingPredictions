"""Strict *local* permission-evidence preflight for NAR daily WIN/PLACE odds.

This NEVER contacts the provider, opens a private licensed CSV/ZIP, uploads
data or proves the provider's legal grant. An attestation and exact-byte
evidence file are a documentary checkpoint; a human must confirm the actual
NAR grant covers each enumerated use. Defaults deny all network requests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from capture_nar_official_daily_preoff_once import NarPreoffDailyHold

_OFFICIAL_ODDS_URL = (
    "https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=daily"
)
_RIGHTS_FILE = "nar_official_daily_odds_rights_PRIVATE.json"
_DOC_NAME = re.compile(
    r"nar_odds_permission_[0-9]{8}_PRIVATE\.(?:pdf|txt|eml)\Z"
)
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_MANDATORY = frozenset({
    "schema", "provider", "endpoint", "permission_evidence_file",
    "permission_evidence_sha256", "issued_on", "valid_until",
    "private_scope_reviewed_by_user", "permit_bounded_automated_download",
    "permit_private_immutable_retention", "permit_private_predictive_research",
    "permit_internal_model_training", "permit_nonidentifying_aggregate_reporting",
    "max_downloads_per_day", "min_seconds_between_downloads",
})


@dataclass(frozen=True)
class LocalOddsPermissionCheckpoint:
    # Technical check of documentation only, NOT confirmation by NAR.
    max_requests_per_day: int
    min_gap_seconds: int
    document_bytes_sha256: str  # PRIVATE, do not emit to public logs.


def _date(value: object) -> date:
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_DATE_INVALID")
    try:
        answer = date.fromisoformat(value)
    except ValueError as exc:
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_DATE_INVALID") from exc
    if answer.isoformat() != value:
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_DATE_INVALID")
    return answer


def verify_private_odds_rights_checkpoint(
    folder: Path, *, requested_day: date,
) -> LocalOddsPermissionCheckpoint:
    """Require scoped local permission document before ANY provider fetch.

    A local note, checkbox or arbitrary SHA256 is not itself proof that
    the provider granted rights. Explicit human review is still required.
    """
    if (not isinstance(folder, Path) or not folder.is_dir()
            or folder.is_symlink() or not isinstance(requested_day, date)):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_PRIVATE_FOLDER_INVALID")
    config = folder / _RIGHTS_FILE
    if not config.is_file() or config.is_symlink():
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_DOCUMENTATION_MISSING")
    if config.stat().st_size < 40 or config.stat().st_size > 8192:
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_DOCUMENTATION_INVALID")
    try:
        record = json.loads(config.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_DOCUMENTATION_INVALID") from exc
    if type(record) is not dict or set(record) != _MANDATORY:
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_SCHEMA_INVALID")
    if (record["schema"] != "NAR.PC2.OfficialDailyOddsRights.v1"
            or record["provider"] != "NAR"
            or record["endpoint"] != _OFFICIAL_ODDS_URL):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_SOURCE_SCOPE_INVALID")
    required_scopes = (
        "private_scope_reviewed_by_user",
        "permit_bounded_automated_download",
        "permit_private_immutable_retention",
        "permit_private_predictive_research",
        "permit_internal_model_training",
        "permit_nonidentifying_aggregate_reporting",
    )
    if any(record[k] is not True for k in required_scopes):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_EXPLICIT_SCOPE_MISSING")
    first = _date(record["issued_on"])
    last = (_date(record["valid_until"])
            if record["valid_until"] is not None else None)
    if first > requested_day or (last is not None and
                                 (last < requested_day or last < first)):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_NOT_VALID_ON_RACE_DAY")
    n = record["max_downloads_per_day"]
    gap = record["min_seconds_between_downloads"]
    if (type(n) is not int or not 1 <= n <= 6
            or type(gap) is not int or not 150 <= gap <= 86400):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_ACCESS_LIMITS_INVALID")
    name, digest = (record["permission_evidence_file"],
                    record["permission_evidence_sha256"])
    if (type(name) is not str or not _DOC_NAME.fullmatch(name)
            or type(digest) is not str or not _HASH.fullmatch(digest)):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_EVIDENCE_ID_INVALID")
    evidence = folder / name
    if (not evidence.is_file() or evidence.is_symlink()
            or not 1 <= evidence.stat().st_size <= 5*1024*1024):
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_EVIDENCE_MISSING")
    if sha256(evidence.read_bytes()).hexdigest() != digest:
        raise NarPreoffDailyHold("NAR_ODDS_RIGHTS_EVIDENCE_HASH_MISMATCH")
    return LocalOddsPermissionCheckpoint(
        max_requests_per_day=n, min_gap_seconds=gap,
        document_bytes_sha256=digest,
    )
