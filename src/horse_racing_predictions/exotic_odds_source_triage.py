"""Metadata-only triage for potential free, lawful pre-decision exotic odds.

Never contacts providers, opens race data, authorizes acquisition, computes EV,
or changes Forward Paper. Every claim is self-attested until human verification.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from urllib.parse import urlsplit

_REQUIRED_TEXT = (
    "provider_name", "terms_reference", "source_reference",
    "race_id_mapping", "combination_mapping", "capture_clock_evidence",
    "purchase_cutoff_reference", "retention_policy_reference",
)
_REQUIRED_TRUE = (
    "free_access_confirmed", "automated_capture_permitted",
    "ml_research_permitted", "snapshot_retention_permitted",
    "pre_decision_quotes_available", "purchase_availability_verified",
    "immutable_capture_supported",
)
_ALLOWED = set(_REQUIRED_TEXT) | set(_REQUIRED_TRUE) | {
    "provider_refresh_seconds", "access_cost_yen", "rights_reviewed_at",
    "source_kind",
}


def _https_reference(value: str) -> bool:
    try:
        url = urlsplit(value)
        return (
            url.scheme == "https" and bool(url.hostname)
            and url.username is None and url.password is None
            and not any(char.isspace() for char in value)
        )
    except ValueError:
        return False


def triage_exotic_odds_source(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate asserted source evidence; NEVER approve data collection or EV."""
    blockers: list[str] = []
    if not isinstance(evidence, Mapping):
        return {
            "status": "blocked", "blockers": ["evidence must be an object"],
            "approved_for_acquisition": False, "approved_for_ev": False,
        }

    unexpected = set(evidence) - _ALLOWED
    if unexpected:
        blockers.append("unknown evidence fields are forbidden")
    for key in _REQUIRED_TEXT:
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            blockers.append(f"missing evidence: {key}")
    for key in ("terms_reference", "source_reference", "purchase_cutoff_reference", "retention_policy_reference"):
        value = evidence.get(key)
        if isinstance(value, str) and value.strip() and not _https_reference(value):
            blockers.append(f"invalid HTTPS reference: {key}")
    for key in _REQUIRED_TRUE:
        if evidence.get(key) is not True:
            blockers.append(f"unverified source gate: {key}")
    if type(evidence.get("access_cost_yen")) is not int or evidence["access_cost_yen"] != 0:
        blockers.append("source must have verified zero access cost")
    cadence = evidence.get("provider_refresh_seconds")
    if type(cadence) is not int or not 0 < cadence <= 86400:
        blockers.append("invalid or unknown quote refresh cadence")
    if evidence.get("source_kind") not in (
        "official_public", "public_web", "local_manual", "local_archive",
    ):
        blockers.append("unrecognized source kind")
    value = evidence.get("rights_reviewed_at")
    try:
        if not isinstance(value, str):
            raise ValueError("missing")
        reviewed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if reviewed.utcoffset() is None:
            raise ValueError("timezone required")
    except (ValueError, TypeError):
        blockers.append("rights review timestamp must include timezone")

    return {
        "status": "blocked" if blockers else "human_review_required",
        "blockers": blockers,
        "approved_for_acquisition": False,
        "approved_for_ev": False,
        "note": (
            "Self-reported terms and timestamps are not authorization. "
            "Independently verify rights, identity, retention, source clock, "
            "and purchase-time executability before any real-data use."
        ),
    }
