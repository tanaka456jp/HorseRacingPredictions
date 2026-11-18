"""No-network synthetic-only tests of private NAR odds documentation gate."""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from nar_private_odds_rights_gate import (  # noqa: E402
    _OFFICIAL_ODDS_URL, verify_private_odds_rights_checkpoint,
    NarPreoffDailyHold,
)

DAY = date(2026, 11, 19)


def private_synthetic_checkpoint(tmp_path: Path):
    # A clearly fictional contract fixture, NEVER a real provider grant.
    name = "nar_odds_permission_20261118_PRIVATE.txt"
    data = b"SYNTHETIC TEST ONLY: NO LEGAL PERMISSION HERE"
    (tmp_path / name).write_bytes(data)
    record = {
        "schema": "NAR.PC2.OfficialDailyOddsRights.v1",
        "provider": "NAR", "endpoint": _OFFICIAL_ODDS_URL,
        "permission_evidence_file": name,
        "permission_evidence_sha256": sha256(data).hexdigest(),
        "issued_on": "2026-11-18", "valid_until": "2026-12-01",
        "private_scope_reviewed_by_user": True,
        "permit_bounded_automated_download": True,
        "permit_private_immutable_retention": True,
        "permit_private_predictive_research": True,
        "permit_internal_model_training": True,
        "permit_nonidentifying_aggregate_reporting": True,
        "max_downloads_per_day": 2,
        "min_seconds_between_downloads": 300,
    }
    (tmp_path / "nar_official_daily_odds_rights_PRIVATE.json").write_text(
        json.dumps(record), encoding="utf-8",
    )
    return record


def test_missing_private_rights_document_is_hold_before_network(tmp_path):
    with pytest.raises(NarPreoffDailyHold,match="DOCUMENTATION_MISSING"):
        verify_private_odds_rights_checkpoint(tmp_path,requested_day=DAY)


def test_local_document_checksum_and_limits_are_verified_not_legal_grant(tmp_path):
    private_synthetic_checkpoint(tmp_path)
    result=verify_private_odds_rights_checkpoint(tmp_path,requested_day=DAY)
    assert result.max_requests_per_day == 2
    assert result.min_gap_seconds == 300
    assert len(result.document_bytes_sha256) == 64
    assert not hasattr(result,"provider_permission_verified")


@pytest.mark.parametrize("field,value,reason",[
    ("provider","OTHER","SOURCE_SCOPE_INVALID"),
    ("endpoint","https://example.com/odds","SOURCE_SCOPE_INVALID"),
    ("private_scope_reviewed_by_user",False,"EXPLICIT_SCOPE_MISSING"),
    ("permit_bounded_automated_download",False,"EXPLICIT_SCOPE_MISSING"),
    ("permit_private_immutable_retention",False,"EXPLICIT_SCOPE_MISSING"),
    ("permit_private_predictive_research",False,"EXPLICIT_SCOPE_MISSING"),
    ("permit_internal_model_training",False,"EXPLICIT_SCOPE_MISSING"),
    ("permit_nonidentifying_aggregate_reporting",False,"EXPLICIT_SCOPE_MISSING"),
    ("issued_on","2026-11-20","NOT_VALID_ON_RACE_DAY"),
    ("valid_until","2026-11-18","NOT_VALID_ON_RACE_DAY"),
    ("issued_on","2026-02-30","DATE_INVALID"),
    ("max_downloads_per_day",7,"ACCESS_LIMITS_INVALID"),
    ("max_downloads_per_day",True,"ACCESS_LIMITS_INVALID"),
    ("min_seconds_between_downloads",10,"ACCESS_LIMITS_INVALID"),
    ("permission_evidence_file","../unsafe.txt","EVIDENCE_ID_INVALID"),
    ("permission_evidence_sha256","f"*64,"EVIDENCE_HASH_MISMATCH"),
])
def test_permissions_fail_closed_without_provider_request(
    tmp_path,field,value,reason,
):
    record=private_synthetic_checkpoint(tmp_path)
    record[field]=value
    (tmp_path / "nar_official_daily_odds_rights_PRIVATE.json").write_text(
        json.dumps(record),encoding="utf-8",
    )
    with pytest.raises(NarPreoffDailyHold,match=reason):
        verify_private_odds_rights_checkpoint(tmp_path,requested_day=DAY)


def test_permissions_missing_evidence_holds(tmp_path):
    record=private_synthetic_checkpoint(tmp_path)
    (tmp_path / record["permission_evidence_file"]).unlink()
    with pytest.raises(NarPreoffDailyHold,match="EVIDENCE_MISSING"):
        verify_private_odds_rights_checkpoint(tmp_path,requested_day=DAY)


def test_missing_scope_field_holds(tmp_path):
    record=private_synthetic_checkpoint(tmp_path)
    del record["permit_private_predictive_research"]
    (tmp_path / "nar_official_daily_odds_rights_PRIVATE.json").write_text(
        json.dumps(record),encoding="utf-8",
    )
    with pytest.raises(NarPreoffDailyHold,match="SCHEMA_INVALID"):
        verify_private_odds_rights_checkpoint(tmp_path,requested_day=DAY)


def test_symlink_evidence_holds(tmp_path):
    record=private_synthetic_checkpoint(tmp_path)
    evidence=tmp_path / record["permission_evidence_file"]
    original=tmp_path / "real_private_synthetic_doc.txt"
    original.write_bytes(evidence.read_bytes())
    evidence.unlink()
    try:
        evidence.symlink_to(original)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(NarPreoffDailyHold,match="EVIDENCE_MISSING"):
        verify_private_odds_rights_checkpoint(tmp_path,requested_day=DAY)


def test_live_collector_stops_before_network_if_rights_absent(tmp_path,monkeypatch):
    from capture_nar_official_daily_odds_preoff_once import capture_private_daily_odds_once
    import capture_nar_official_daily_odds_preoff_once as capture
    utc=datetime.now(timezone.utc)
    day=utc.astimezone(capture._JST).date()
    frozen={
        "earliest_off_utc":(utc+timedelta(hours=3)).isoformat(),
        "complete_private_forecasts":[{
            "race_id":"NAR:FICTIONAL",
            "scheduled_off_utc":(utc+timedelta(hours=3)).isoformat(),
        }],
    }
    monkeypatch.setattr(capture,"_load_original_frozen_forecast",
                        lambda folder,date:(frozen,b"FICTIONAL_ONLY"))
    called={"network":False}
    def forbidden(*args,**kwargs):
        called["network"]=True
        raise AssertionError("Network access must never occur")
    monkeypatch.setattr(capture.urllib.request,"urlopen",forbidden)
    with pytest.raises(NarPreoffDailyHold,match="DOCUMENTATION_MISSING"):
        capture_private_daily_odds_once(tmp_path)
    assert called["network"] is False
