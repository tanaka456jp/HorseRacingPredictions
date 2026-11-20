"""Synthetic-only, offline tests for pre-off evidence gates."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

module_path = Path(__file__).resolve().parents[1] / "scripts" / "offline_forward_quote_audit.py"
spec = importlib.util.spec_from_file_location("offline_forward_quote_audit", module_path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_quote_provenance_gates():
    off = datetime(2026, 12, 1, 10, tzinfo=timezone.utc)
    base = dict(race_key="synthetic-A", market="WIN", quote=2.4,
                source_time=off - timedelta(minutes=5),
                received_time=off - timedelta(minutes=4),
                off_time=off, registered_races={"synthetic-A"})
    assert audit.audit_quote(**base) == "INDICATIVE_ONLY"
    assert audit.audit_quote(**{**base, "quote": None}) == "MISSING_PRICE"
    assert audit.audit_quote(**{**base, "market": "OTHER"}) == "INVALID_MARKET"
    assert audit.audit_quote(**{**base, "received_time": off}) == "AFTER_CUTOFF"
    assert audit.audit_quote(**{**base, "source_time": off - timedelta(minutes=3)}) == "SOURCE_AFTER_RECEIPT"
    assert audit.audit_quote(**{**base, "source_time": off.replace(tzinfo=None)}) == "INVALID_TIMESTAMP"
    assert audit.audit_quote(**{**base, "race_key": "synthetic-B"}) == "UNREGISTERED_RACE"


def test_denominator_never_shrinks_for_missing():
    result = audit.audit_manifest(registered_races=["a", "b", "c"],
                                  observed_races=["a", "unregistered"])
    assert result == {"status": "UNEXPECTED_OBSERVATION", "registered": 3, "observed": 1,
                      "missing": 2, "unexpected": 1}
    assert audit.audit_manifest(registered_races=["a", "a"], observed_races=[])["status"] == "DUPLICATE_REGISTRATION"


def test_duplicate_observations_block_audit_without_exposing_ids():
    result = audit.audit_manifest(registered_races=["a", "b"],
                                  observed_races=["a", "a"])
    assert result == {"status": "DUPLICATE_OBSERVATION", "registered": 2,
                      "observed": 1, "missing": 1, "unexpected": 0}


def test_empty_registration_cannot_pass_as_complete():
    assert audit.audit_manifest(registered_races=[], observed_races=[]) == {
        "status": "EMPTY_REGISTRATION", "registered": 0, "observed": 0,
        "missing": 0, "unexpected": 0}
    assert audit.audit_manifest(registered_races=[], observed_races=["unexpected"]) == {
        "status": "EMPTY_REGISTRATION", "registered": 0, "observed": 0,
        "missing": 0, "unexpected": 1}


def test_missing_observations_are_not_marked_complete():
    assert audit.audit_manifest(registered_races=["a", "b"], observed_races=["a"]) == {
        "status": "MISSING_OBSERVATION", "registered": 2, "observed": 1,
        "missing": 1, "unexpected": 0,
    }


def test_decimal_odds_below_one_are_invalid():
    off = datetime(2026, 12, 1, 10, tzinfo=timezone.utc)
    args = dict(race_key="synthetic-A", market="PLACE", quote=0.75,
                source_time=off - timedelta(minutes=5),
                received_time=off - timedelta(minutes=4),
                off_time=off, registered_races={"synthetic-A"})
    assert audit.audit_quote(**args) == "INVALID_PRICE"
    assert audit.audit_quote(**{**args, "quote": 1.0}) == "INDICATIVE_ONLY"


def test_duplicate_registration_retains_original_denominator_and_missing_count():
    result = audit.audit_manifest(registered_races=["a", "a", "b"],
                                  observed_races=["a"])
    assert result == {"status": "DUPLICATE_REGISTRATION", "registered": 3,
                      "observed": 1, "missing": 1, "unexpected": 0}


def test_complete_manifest_only_is_ok():
    assert audit.audit_manifest(registered_races=["a", "b"], observed_races=["b", "a"]) == {
        "status": "OK", "registered": 2, "observed": 2, "missing": 0, "unexpected": 0,
    }


def test_scalar_manifest_inputs_fail_closed_without_splitting_race_ids():
    invalid = {"status": "INVALID_MANIFEST", "registered": 0,
               "observed": 0, "missing": 0, "unexpected": 0}
    assert audit.audit_manifest(registered_races="race-A", observed_races="race-A") == invalid
    assert audit.audit_manifest(registered_races=["race-A"], observed_races="race-A") == invalid
    assert audit.audit_manifest(registered_races=b"race-A", observed_races=[]) == invalid
    assert audit.audit_manifest(registered_races=["race-A"], observed_races=["race-A"]) == {
        "status": "OK", "registered": 1, "observed": 1,
        "missing": 0, "unexpected": 0,
    }


def test_malformed_manifest_identifiers_fail_closed():
    invalid = {"status": "INVALID_MANIFEST", "registered": 0,
               "observed": 0, "missing": 0, "unexpected": 0}
    assert audit.audit_manifest(registered_races=None, observed_races=[]) == invalid
    assert audit.audit_manifest(registered_races=[["nested"]], observed_races=[]) == invalid
    assert audit.audit_manifest(registered_races=["race-A"], observed_races=[{"key": "private"}]) == invalid


def test_quote_malformed_registration_fails_closed():
    off = datetime(2026, 12, 1, 10, tzinfo=timezone.utc)
    base = dict(race_key="synthetic-A", market="WIN", quote=2.4,
                source_time=off - timedelta(minutes=5),
                received_time=off - timedelta(minutes=4),
                off_time=off, registered_races=["synthetic-A"])
    assert audit.audit_quote(**base) == "INDICATIVE_ONLY"
    for roster in (None, "synthetic-A", [["nested"]], [], ["synthetic-A", "synthetic-A"]):
        assert audit.audit_quote(**{**base, "registered_races": roster}) == "INVALID_MANIFEST"
    assert audit.audit_quote(**{**base, "race_key": ["unhashable"]}) == "UNREGISTERED_RACE"


def test_blank_or_nonstr_race_identifiers_never_pass_manifest_gate():
    invalid = {"status": "INVALID_MANIFEST", "registered": 0,
               "observed": 0, "missing": 0, "unexpected": 0}
    for roster, observed in [([None], [None]), ([""], [""]), (["   "], []),
                             (["synthetic-A"], [None]), ([123], [123])]:
        assert audit.audit_manifest(registered_races=roster,
                                    observed_races=observed)["status"] == "INVALID_MANIFEST"
    off = datetime(2026, 12, 1, 10, tzinfo=timezone.utc)
    args = dict(race_key="synthetic-A", market="WIN", quote=2.4,
                source_time=off - timedelta(minutes=5),
                received_time=off - timedelta(minutes=4),
                off_time=off)
    for roster in ([None, "synthetic-A"], ["", "synthetic-A"],
                   ["   ", "synthetic-A"], [123, "synthetic-A"]):
        assert audit.audit_quote(**args, registered_races=roster) == "INVALID_MANIFEST"
