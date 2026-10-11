"""Synthetic-only provenance tests: never read racing data or holdout."""
import pytest
from horse_racing_predictions.phase11_provenance_triage import (
    REQUIRED_EVIDENCE, triage_provenance,
)

def fixture(**changes):
    evidence = dict(
        source_name="SYNTHETIC", source_homepage="https://example.org/source",
        provider_identity="Synthetic", license_evidence_url="https://example.org/terms",
        rights_review_notes="Synthetic test only",
        coverage_start="2017-01-01", coverage_end="2024-12-31",
        acquisition_method="Synthetic only", source_fingerprint_sha256="a"*64,
        independent_of_combined_history=True, rights_permit_research_ml=True,
        rights_permit_automated_acquisition=True,
        derived_by_filtering_current_history=False,
    )
    evidence.update(changes)
    return evidence

def inspect(evidence):
    result = triage_provenance(evidence)
    assert result["approved_for_phase11"] is False
    assert result["data_read_permitted"] is False
    return result

def test_complete_synthetic_metadata_still_requires_human_review():
    assert inspect(fixture())["status"] == "human_review_required"

@pytest.mark.parametrize("field", REQUIRED_EVIDENCE)
def test_missing_metadata_blocks(field):
    data = fixture()
    data.pop(field)
    assert inspect(data)["status"] == "blocked"

@pytest.mark.parametrize("field", ["source_homepage", "license_evidence_url"])
@pytest.mark.parametrize("value", ["http://example.org", "https://u:p@example.org", "not-a-url"])
def test_invalid_evidence_urls_block(field, value):
    assert inspect(fixture(**{field: value}))["status"] == "blocked"

@pytest.mark.parametrize("start,end", [
    ("2017-01-02", "2024-12-31"),
    ("2017-01-01", "2024-12-30"),
    ("2017-01-01", "2025-01-01"),
    ("invalid", "2024-12-31"),
])
def test_incomplete_or_holdout_coverage_blocks(start, end):
    assert inspect(fixture(coverage_start=start, coverage_end=end))["status"] == "blocked"

@pytest.mark.parametrize("field,value", [
    ("independent_of_combined_history", False),
    ("rights_permit_research_ml", False),
    ("rights_permit_automated_acquisition", False),
    ("derived_by_filtering_current_history", True),
])
def test_unverified_rights_or_independence_blocks(field, value):
    assert inspect(fixture(**{field: value}))["status"] == "blocked"

@pytest.mark.parametrize("fingerprint", ["a"*63, "g"*64, "not-a-digest"])
def test_invalid_digest_blocks(fingerprint):
    assert inspect(fixture(source_fingerprint_sha256=fingerprint))["status"] == "blocked"

@pytest.mark.parametrize("value", [None, [], "not-an-object"])
def test_non_mapping_blocks(value):
    assert inspect(value)["status"] == "blocked"
