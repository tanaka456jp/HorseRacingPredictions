"""Offline intake for *independently licensed* third-party racing CSVs.

No automatic download, scraper, service request, JV-Link call, note action or
GitHub upload. All input is local and explicitly nominated by the operator.
A signed/claimed permission manifest is evidence for review, NOT a legal grant
or approval for training; candidate inputs remain quarantined until separately
reviewed. Protected 2025+ holdout is never accepted by this module.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from .pre2025_training_csv_audit import (
    CUTOFF, MAX_BYTES, REQUIRED_ALIASES, UnsafeTrainingSource,
    _date_cell, audit_pre2025_training_csv,
)

_MAX_MANIFEST_BYTES = 8192
_MAX_PAYOUT_ROWS = 3_000_000
_KINDS = frozenset({"history", "settlement"})
_ISSUERS = frozenset({"own_observations", "rightsholder_licensed", "verified_open_data"})
_RIGHTS_SCOPES = frozenset({"private_noncommercial_research"})
_MARKERS = (
    "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING", "INCOMPLETE_DO_NOT_USE",
    "DO_NOT_TRAIN_OR_REPOST", "INCOMPLETE_DO_NOT_TRAIN",
)
_PROVIDER_DENY = re.compile(
    r"jra.?van|jv.?link|netkeiba|jravan|地方競馬data", re.IGNORECASE,
)
_REQUIRED_MANIFEST = frozenset({
    "schema_version", "kind", "provider_id", "source_category",
    "rights_holder", "acquisition_method", "rights_evidence_ref",
    "rights_scope", "local_ml_permitted", "retention_permitted",
    "contract_valid_through", "source_sha256",
})


@dataclass(frozen=True)
class AlternativeIntakeReport:
    status: str
    kind: str
    total_rows: int
    min_year: int
    max_year: int
    source_digest_matches: bool
    operator_claims_private_ml_rights: bool
    actual_source_rights_independently_verified: bool = False
    approved_for_model_training: bool = False
    paid_service_invoked: bool = False
    web_data_downloaded: bool = False
    published_to_note: bool = False
    protected_holdout_opened: bool = False


def _is_untrusted_path(path: Path) -> bool:
    return (
        not isinstance(path, Path) or not path.is_absolute()
        or path.is_symlink()
        or any(p.is_symlink() for p in path.parents)
        or not path.is_file()
        or any(p.name.lower() in {
            "holdout", "final-evaluation", "2025-2026-holdout",
            "jravan-private-quarantine",
        } for p in path.parents)
        or any((p / mark).exists()
               for p in path.parents for mark in _MARKERS)
    )


def _manifest(path: Path) -> dict:
    if _is_untrusted_path(path) or path.suffix.lower() != ".json":
        raise UnsafeTrainingSource("ALTERNATIVE_MANIFEST_PATH_INVALID")
    if not 0 < path.stat().st_size <= _MAX_MANIFEST_BYTES:
        raise UnsafeTrainingSource("ALTERNATIVE_MANIFEST_SIZE_INVALID")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError):
        raise UnsafeTrainingSource("ALTERNATIVE_MANIFEST_UNREADABLE") from None
    if not isinstance(payload, dict) or set(payload) != _REQUIRED_MANIFEST:
        raise UnsafeTrainingSource("ALTERNATIVE_MANIFEST_SCHEMA_INVALID")
    return payload


def _verify_claims(payload: dict, kind: str, today: date) -> None:
    if (payload["schema_version"] != 1 or payload["kind"] != kind
            or kind not in _KINDS or payload["source_category"] not in _ISSUERS
            or payload["rights_scope"] not in _RIGHTS_SCOPES):
        raise UnsafeTrainingSource("ALTERNATIVE_SOURCE_TYPE_OR_SCOPE_INVALID")
    for field in ("provider_id", "rights_holder",
                  "acquisition_method", "rights_evidence_ref"):
        value = payload[field]
        if (not isinstance(value, str) or not 3 <= len(value) <= 128
                or not value.strip()
                or any(ord(c) < 32 for c in value)):
            raise UnsafeTrainingSource("ALTERNATIVE_SOURCE_EVIDENCE_MISSING")
    if _PROVIDER_DENY.search(payload["provider_id"]):
        raise UnsafeTrainingSource("KNOWN_PROVIDER_REQUIRES_SEPARATE_REVIEW")
    if (payload["local_ml_permitted"] is not True
            or payload["retention_permitted"] is not True):
        raise UnsafeTrainingSource("PRIVATE_RESEARCH_RIGHTS_NOT_ATTESTED")
    term = payload["contract_valid_through"]
    if term == "perpetual":
        # An operator attestation does not prove perpetual upstream rights.
        if payload["source_category"] != "verified_open_data":
            raise UnsafeTrainingSource("PERPETUAL_LICENSE_UNVERIFIED")
    else:
        if not isinstance(term, str):
            raise UnsafeTrainingSource("SOURCE_LICENSE_TERM_INVALID")
        try:
            expiration = date.fromisoformat(term)
        except ValueError:
            raise UnsafeTrainingSource("SOURCE_LICENSE_TERM_INVALID") from None
        if expiration.isoformat() != term or expiration < today:
            raise UnsafeTrainingSource("SOURCE_RIGHTS_EXPIRED")
    digest = payload["source_sha256"]
    if (not isinstance(digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", digest) is None):
        raise UnsafeTrainingSource("ALTERNATIVE_SOURCE_DIGEST_REQUIRED")


def _settlement_audit(csv_path: Path) -> tuple[int, int, int]:
    required = (
        "race_id", "race_date", "horse_name",
        "win_return_per_100_yen", "place_return_per_100_yen",
    )
    errors: list[str] = []
    for enc in ("utf-8-sig", "cp932", "euc_jp"):
        try:
            with csv_path.open("r", encoding=enc, newline="", errors="strict") as f:
                reader = csv.reader(f, strict=True)
                try:
                    header = [x.strip().lstrip("\ufeff") for x in next(reader)]
                except (csv.Error, StopIteration):
                    raise UnsafeTrainingSource("SETTLEMENT_HEADER_MISSING") from None
                if (len(header) != len(set(header))
                        or not set(required).issubset(header)
                        or len(header) > 100):
                    raise UnsafeTrainingSource("SETTLEMENT_SCHEMA_INVALID")
                cols = [header.index(name) for name in required]
                n = 0
                min_year, max_year = 9999, 0
                seen: set[tuple[str, str]] = set()
                for row in reader:
                    n += 1
                    if n > _MAX_PAYOUT_ROWS or len(row) != len(header):
                        raise UnsafeTrainingSource("SETTLEMENT_ROW_INVALID")
                    rid, day_raw, horse, win_raw, place_raw = (row[i] for i in cols)
                    day = _date_cell(day_raw)
                    if day > CUTOFF:
                        raise UnsafeTrainingSource("PROTECTED_HOLDOUT_IN_SOURCE")
                    if not rid.strip() or not horse.strip():
                        raise UnsafeTrainingSource("SETTLEMENT_IDENTITY_MISSING")
                    key = (rid, horse)
                    if key in seen:
                        raise UnsafeTrainingSource("DUPLICATE_SETTLEMENT_ROW")
                    seen.add(key)
                    for amount in (win_raw, place_raw):
                        if not amount.isdecimal() or int(amount) < 0:
                            raise UnsafeTrainingSource("SETTLEMENT_PAYOUT_INVALID")
                    min_year = min(min_year, day.year)
                    max_year = max(max_year, day.year)
                if n == 0:
                    raise UnsafeTrainingSource("SETTLEMENT_EMPTY")
                return n, min_year, max_year
        except UnicodeDecodeError:
            errors.append("BAD_ENCODING")
        except csv.Error:
            raise UnsafeTrainingSource("SETTLEMENT_ROW_INVALID") from None
    raise UnsafeTrainingSource("SETTLEMENT_ENCODING_INVALID") from None


def inspect_alternative_csv(
    source_csv: Path, manifest_json: Path, *,
    kind: str, today: date | None = None,
) -> AlternativeIntakeReport:
    """Read-only private source inspection; never admits data to training.

    The manifest must contain a private SHA256 fingerprint established by
    an operator independently of this validator. Do not upload that manifest.
    Existing third-party archives with unknown lineage must fail closed.
    """
    if (kind not in _KINDS or _is_untrusted_path(source_csv)
            or source_csv.suffix.lower() != ".csv"
            or source_csv == manifest_json):
        raise UnsafeTrainingSource("ALTERNATIVE_SOURCE_PATH_INVALID")
    size = source_csv.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise UnsafeTrainingSource("ALTERNATIVE_SOURCE_SIZE_INVALID")
    payload = _manifest(manifest_json)
    _verify_claims(payload, kind, today or date.today())
    # Complete *structural* audit precedes any digest match. No source cells
    # or private original filenames are included in errors or the report.
    if kind == "history":
        result = audit_pre2025_training_csv(source_csv)
        n, min_year, max_year, digest = (
            result.checked_rows, result.min_year,
            result.max_year, result.sha256,
        )
    else:
        n, min_year, max_year = _settlement_audit(source_csv)
        with source_csv.open("rb") as stream:
            digest = sha256(stream.read()).hexdigest()
    if (source_csv.stat().st_size != size
            or digest != payload["source_sha256"]):
        raise UnsafeTrainingSource("ALTERNATIVE_SOURCE_DIGEST_MISMATCH")
    return AlternativeIntakeReport(
        status="PRIVATE_OPERATOR_REVIEW_ONLY_NOT_TRAINING_APPROVAL",
        kind=kind, total_rows=n, min_year=min_year,
        max_year=max_year, source_digest_matches=True,
        operator_claims_private_ml_rights=True,
    )
