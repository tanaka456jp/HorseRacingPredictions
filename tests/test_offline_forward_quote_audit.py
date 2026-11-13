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
    assert result == {"status": "OK", "registered": 3, "observed": 1,
                      "missing": 2, "unexpected": 1}
    assert audit.audit_manifest(registered_races=["a", "a"], observed_races=[])["status"] == "DUPLICATE_REGISTRATION"
