"""Metadata-only, fail-closed triage for independent Phase 11 research sources.

This module never opens CSVs, historical race rows, or the final holdout.
Even complete metadata can only trigger human review, never data approval.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping
from urllib.parse import urlsplit

REQUIRED_EVIDENCE = (
    "source_name", "source_homepage", "provider_identity",
    "license_evidence_url", "rights_review_notes", "coverage_start",
    "coverage_end", "acquisition_method", "source_fingerprint_sha256",
)


def triage_provenance(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Review evidence metadata only; never authorize a real-data read."""
    blockers: list[str] = []
    if not isinstance(evidence, Mapping):
        return {
            "status": "blocked",
            "blockers": ["evidence must be an object"],
            "approved_for_phase11": False,
            "data_read_permitted": False,
        }

    for field in REQUIRED_EVIDENCE:
        if not isinstance(evidence.get(field), str) or not evidence[field].strip():
            blockers.append(f"missing evidence: {field}")

    for field in ("source_homepage", "license_evidence_url"):
        value = evidence.get(field)
        if isinstance(value, str) and value.strip():
            try:
                url = urlsplit(value)
                valid_url = (
                    url.scheme == "https" and bool(url.hostname)
                    and url.username is None and url.password is None
                    and not any(ch.isspace() for ch in value)
                )
            except ValueError:
                valid_url = False
            if not valid_url:
                blockers.append(f"invalid HTTPS evidence URL: {field}")

    try:
        start = date.fromisoformat(evidence["coverage_start"])
        end = date.fromisoformat(evidence["coverage_end"])
        if start > end or start > date(2017, 1, 1) or end < date(2024, 12, 31):
            blockers.append("coverage insufficient for 2017-2024 research protocol")
        if end > date(2024, 12, 31):
            blockers.append("source coverage includes post-2024 final holdout period")
    except (KeyError, ValueError, TypeError):
        blockers.append("invalid ISO calendar coverage")

    fingerprint = evidence.get("source_fingerprint_sha256")
    if isinstance(fingerprint, str) and fingerprint.strip():
        if len(fingerprint) != 64 or any(c not in "0123456789abcdefABCDEF" for c in fingerprint):
            blockers.append("invalid SHA-256 fingerprint")

    if evidence.get("independent_of_combined_history") is not True:
        blockers.append("independence from combined history is not attested")
    if evidence.get("rights_permit_research_ml") is not True:
        blockers.append("ML research use rights not affirmatively reviewed")
    if evidence.get("rights_permit_automated_acquisition") is not True:
        blockers.append("automated acquisition rights not affirmatively reviewed")
    if evidence.get("derived_by_filtering_current_history") is not False:
        blockers.append("source must not be derived from current_history")

    return {
        "status": "blocked" if blockers else "human_review_required",
        "blockers": blockers,
        "approved_for_phase11": False,
        "data_read_permitted": False,
        "note": "Evidence fields are self-assertions, not independently verified rights or provenance.",
    }
