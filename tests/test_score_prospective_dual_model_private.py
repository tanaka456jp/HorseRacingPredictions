"""Entirely fictional offline paper settlement for a frozen future card."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import score_prospective_dual_model_private as S  # noqa: E402
import freeze_prospective_dual_catboost_private as F  # noqa: E402
from test_freeze_prospective_dual_catboost_private import setup, NOW, RACE


def make_files(tmp_path,monkeypatch):
    args=setup(tmp_path,monkeypatch)
    F.freeze_private_future(**args)
    frozen=tmp_path/"20261206_JRA_dual_catboost_PRIVATE.json"
    results=tmp_path/"postevent.json"
    doc={
        "schema":"HorseRacing.PC2.ReviewedOfficialResults.v1",
        "jurisdiction":"JRA",
        "race_day_jst":"2026-12-06",
        "observed_postevent_utc":(NOW+timedelta(hours=3)).isoformat(),
        "operator_reviewed_official_results":True,
        "independently_verified_source_provenance":False,
        "official_races":{RACE:{
            "finish_by_horse":{"1":4,"2":3,"3":2,"4":1},
            "selected_top1_win_return_per_100_yen":250,
        }},
    }
    results.write_text(json.dumps(doc),encoding="utf-8")
    return frozen,results


def test_private_frozen_actual_model_pred_and_full_official_return(tmp_path,monkeypatch):
    frozen,results=make_files(tmp_path,monkeypatch)
    result=S.score_private_forward_files(frozen,results)
    assert result["status"].startswith("COMPLETE_DESCRIPTIVE")
    assert result["top1_win_hits"]==1
    assert result["top1_win_hit_rate"]==1.0
    assert result["top3_numeric_podium_hits"]==3
    assert result["stake_yen"]==100
    assert result["official_paper_returns_yen"]==250
    assert result["paper_roi_after_stake"]==1.5
    assert result["positive_expected_value_proven"] is False
    assert result["independent_prediction_receipt_verified"] is False
    assert result["source_data_uploaded"] is False


def test_frozen_prediction_tamper_rejected(tmp_path,monkeypatch):
    frozen,results=make_files(tmp_path,monkeypatch)
    doc=json.loads(frozen.read_text(encoding="utf-8"))
    doc["frozen_shadow_PRIVATE"]["races"][0]["top3"][0]="1"
    frozen.write_text(json.dumps(doc),encoding="utf-8")
    with pytest.raises(ValueError,match="COMMITMENT"):
        S.score_private_forward_files(frozen,results)


def test_missing_official_results_never_produce_cherrypicked_roi(tmp_path,monkeypatch):
    frozen,results=make_files(tmp_path,monkeypatch)
    doc=json.loads(results.read_text(encoding="utf-8"))
    doc["official_races"]={}
    results.write_text(json.dumps(doc),encoding="utf-8")
    with pytest.raises(Exception,match="DENOMINATOR"):
        S.score_private_forward_files(frozen,results)
