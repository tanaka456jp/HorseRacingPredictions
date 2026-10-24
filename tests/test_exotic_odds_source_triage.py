"""Synthetic-only source-rights triage; no provider access or race data."""
import pytest

from horse_racing_predictions.exotic_odds_source_triage import (
    triage_exotic_odds_source,
)


def candidate(**changes):
    evidence = {
        "provider_name": "SYNTHETIC PROVIDER",
        "terms_reference": "https://example.invalid/terms",
        "source_reference": "https://example.invalid/quotes",
        "race_id_mapping": "documented synthetic race key",
        "combination_mapping": "trio unordered, trifecta ordered",
        "capture_clock_evidence": "synthetic NTP clock description",
        "purchase_cutoff_reference": "https://example.invalid/cutoff",
        "retention_policy_reference": "https://example.invalid/retention",
        "free_access_confirmed": True,
        "automated_capture_permitted": True,
        "ml_research_permitted": True,
        "snapshot_retention_permitted": True,
        "pre_decision_quotes_available": True,
        "purchase_availability_verified": True,
        "immutable_capture_supported": True,
        "provider_refresh_seconds": 300,
        "access_cost_yen": 0,
        "rights_reviewed_at": "2024-01-01T00:00:00+09:00",
        "source_kind": "official_public",
    }
    evidence.update(changes)
    return evidence


def inspect(value):
    result = triage_exotic_odds_source(value)
    assert result["approved_for_acquisition"] is False
    assert result["approved_for_ev"] is False
    return result


def test_complete_self_attestation_still_requires_independent_human_review():
    result = inspect(candidate())
    assert result["status"] == "human_review_required"
    assert result["blockers"] == []


@pytest.mark.parametrize("field", [
    "free_access_confirmed", "automated_capture_permitted",
    "ml_research_permitted", "snapshot_retention_permitted",
    "pre_decision_quotes_available", "purchase_availability_verified",
    "immutable_capture_supported",
])
@pytest.mark.parametrize("value", [False, None, 1, "true"])
def test_every_rights_gate_requires_exact_true(field, value):
    assert inspect(candidate(**{field: value}))["status"] == "blocked"


@pytest.mark.parametrize("field", [
    "provider_name", "terms_reference", "source_reference",
    "race_id_mapping", "combination_mapping", "capture_clock_evidence",
    "purchase_cutoff_reference", "retention_policy_reference",
])
def test_required_source_evidence_cannot_be_empty(field):
    assert inspect(candidate(**{field: "  "}))["status"] == "blocked"


@pytest.mark.parametrize("field", [
    "terms_reference", "source_reference", "purchase_cutoff_reference",
    "retention_policy_reference",
])
@pytest.mark.parametrize("url", [
    "http://example.invalid", "https://user:pass@example.invalid",
    "https://example.invalid/has space", "not-a-url",
])
def test_reference_must_be_https_without_credentials_or_whitespace(field, url):
    assert inspect(candidate(**{field: url}))["status"] == "blocked"


@pytest.mark.parametrize("cost", [-1, 1, None, True, "0", 0.0])
def test_paid_or_ambiguous_access_is_blocked(cost):
    assert inspect(candidate(access_cost_yen=cost))["status"] == "blocked"


@pytest.mark.parametrize("cadence", [0, -1, 86401, None, True, "300"])
def test_unknown_or_invalid_refresh_cadence_is_blocked(cadence):
    assert inspect(candidate(provider_refresh_seconds=cadence))["status"] == "blocked"


@pytest.mark.parametrize("reviewed_at", [
    "2024-01-01T00:00:00", "not-a-time", None, 42,
])
def test_rights_review_timestamp_must_be_timezone_aware(reviewed_at):
    assert inspect(candidate(rights_reviewed_at=reviewed_at))["status"] == "blocked"


def test_unknown_nested_evidence_is_not_accepted():
    assert inspect(candidate(result_payload={"winning": [1, 2, 3]}))["status"] == "blocked"


def test_non_mapping_is_blocked():
    assert inspect(None)["status"] == "blocked"


def test_unrecognized_source_kind_is_blocked():
    assert inspect(candidate(source_kind="final_payout"))["status"] == "blocked"
