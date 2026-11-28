"""Synthetic-only tests of the restricted private input adapter."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from horse_racing_predictions.nar_nonfavorite_win_policy import NonfavoriteWinRace
from evaluate_nar_nonfavorite_preoff_local import audit_private_file

UTC = timezone.utc


def sample():
    off = datetime(2026, 11, 19, 5, tzinfo=UTC)
    return NonfavoriteWinRace(
        race_id="TEST:FAKE", race_day_jst="2026-11-19",
        top_win_horse="7", entrants=8,
        forecast_frozen_utc=off-timedelta(hours=2),
        hosted_forecast_receipt_utc=off-timedelta(hours=1),
        scheduled_off_utc=off,
        selected_preoff_popularity=2,
        selected_preoff_win_odds=4.3,
        official_market_source_utc=off-timedelta(minutes=22),
        locally_received_market_utc=off-timedelta(minutes=20),
        settlement_status="FINISHED",
        official_win_return_per_100_yen=600,
    )


def write_input(tmp_path, rows):
    record={
        "schema":"NAR.PC2.PrivateNonfavoriteForwardEvidence.v1",
        "input_mode":"LOCAL_PERSONAL_MANUAL_PREOFF_SOURCE",
        "frozen_race_days":{"TEST:FAKE":"2026-11-19"},
        "observations":rows,
        "ticket_unit_yen":100,
        "market_observations_preoff_only":True,
        "forecast_registered_before_off":True,
    }
    path=tmp_path/"synthetic_private_test.json"
    path.write_text(json.dumps(record),encoding="utf-8")
    return path,record


def test_no_data_ever_faked_and_single_only_nonfavorite_has_hold(tmp_path):
    obj=asdict(sample())
    for k,v in obj.items():
        if isinstance(v,datetime):
            obj[k]=v.isoformat()
    path,_=write_input(tmp_path,[obj])
    result=audit_private_file(path)
    assert result.frozen_races==1
    assert result.full_policy_paper_roi==5.0
    assert result.nonfavorite_policy_paper_roi==5.0
    assert result.market_execution_verified is False
    assert result.after_cost_positive_expected_value_proven is False


def test_private_file_rejects_postevent_popularity_and_missing_manifest(tmp_path):
    obj=asdict(sample())
    for k,v in obj.items():
        if isinstance(v,datetime):
            obj[k]=v.isoformat()
    obj["locally_received_market_utc"]=obj["scheduled_off_utc"]
    path,record=write_input(tmp_path,[obj])
    result=audit_private_file(path)
    assert result.status.startswith("HOLD")
    assert result.full_policy_paper_roi is None
    record["frozen_race_days"]={}
    path.write_text(json.dumps(record),encoding="utf-8")
    with pytest.raises(ValueError,match="INVALID_FROZEN_RACE_MANIFEST"):
        audit_private_file(path)


def test_adapter_rejects_nonmanual_or_extra_fields(tmp_path):
    obj=asdict(sample())
    for k,v in obj.items():
        if isinstance(v,datetime):
            obj[k]=v.isoformat()
    path,record=write_input(tmp_path,[obj])
    record["input_mode"]="AUTO_SCRAPE"
    path.write_text(json.dumps(record),encoding="utf-8")
    with pytest.raises(ValueError,match="PREOFF_SCOPE"):
        audit_private_file(path)
    record["input_mode"]="LOCAL_PERSONAL_MANUAL_PREOFF_SOURCE"
    record["observations"][0]["raw_odds_zip_path"]="SHOULD_NEVER_ACCEPT"
    path.write_text(json.dumps(record),encoding="utf-8")
    with pytest.raises(ValueError,match="RACE_EVIDENCE_SCHEMA"):
        audit_private_file(path)
