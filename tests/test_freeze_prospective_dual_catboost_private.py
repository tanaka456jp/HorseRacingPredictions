"""Private-only freeze contract: no web, no trained model bytes exported."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import freeze_prospective_dual_catboost_private as S  # noqa: E402
from horse_racing_predictions.modeling import CatBoostProbabilityModel

UTC = timezone.utc
NOW = datetime(2026, 12, 6, 1, tzinfo=UTC)
RACE = "JRA-20261206-KYOTO-01"


class FakeNative:
    def __init__(self, column):
        self.column = column

    def predict(self, x, prediction_type):
        assert prediction_type == "RawFormulaVal"
        return x[self.column].to_numpy(dtype=float)


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    m = CatBoostProbabilityModel(feature_columns=["past_starts","past_top3_rate"])
    n = CatBoostProbabilityModel(feature_columns=["past_starts","past_top3_rate"])
    m.model, n.model = FakeNative("past_starts"), FakeNative("past_top3_rate")
    monkeypatch.setattr(S, "load_dual_research_candidate", lambda _: SimpleNamespace(
        winner=m, outsider=n, train_end="2022-12-31",
        digest_by_role={"win.cbm":"a"*64, "outsider.cbm":"b"*64},
    ))
    pd.DataFrame([
        dict(race_id=RACE, horse_id=str(i), past_starts=i, past_top3_rate=5-i)
        for i in (1,2,3,4)
    ]).to_csv(tmp_path/"features.csv",index=False)
    manifest = {
        "schema":"HorseRacing.PrivateFutureCalendar.v1",
        "jurisdiction":"JRA",
        "race_day_jst":"2026-12-06",
        "source_asof_utc":(NOW-timedelta(minutes=1)).isoformat(),
        "scheduled_off_utc":{RACE:(NOW+timedelta(hours=1)).isoformat()},
        "runner_count_by_race":{RACE:4},
        "operator_reviewed_asof_only":True,
        "operator_reviewed_complete_roster":True,
    }
    (tmp_path/"calendar.json").write_text(json.dumps(manifest),encoding="utf-8")
    return dict(
        candidate_dir=tmp_path, features_csv=tmp_path/"features.csv",
        calendar_json=tmp_path/"calendar.json",
        private_output_dir=tmp_path, now_utc=NOW,
    )


def test_actual_wrapper_inference_saved_privately_once(tmp_path,monkeypatch):
    args = setup(tmp_path,monkeypatch)
    summary = S.freeze_private_future(**args)
    assert summary["status"].startswith("PRIVATE_FITTED_MODEL_FORECAST")
    assert summary["races"] == 1
    assert summary["runners"] == 4
    assert len(summary["blinded_digest"]) == 64
    assert summary["positive_ev_proven"] is False
    saved = tmp_path / "20261206_JRA_dual_catboost_PRIVATE.json"
    doc = json.loads(saved.read_text(encoding="utf-8"))
    assert doc["frozen_shadow_PRIVATE"]["races"][0]["top3"] == ["4", "3", "2"]
    assert doc["hosted_preoff_receipt_verified"] is False
    assert doc["raw_source_uploaded"] is False
    with pytest.raises(FileExistsError):
        S.freeze_private_future(**args)


def test_roster_incomplete_and_retroactive_feature_review_fail_closed(tmp_path,monkeypatch):
    args = setup(tmp_path,monkeypatch)
    path = args["calendar_json"]
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["runner_count_by_race"][RACE] = 5
    path.write_text(json.dumps(obj),encoding="utf-8")
    with pytest.raises(ValueError, match="ROSTER_COVERAGE"):
        S.freeze_private_future(**args)
    assert not (tmp_path/"20261206_JRA_dual_catboost_PRIVATE.json").exists()
    obj["runner_count_by_race"][RACE] = 4
    obj["operator_reviewed_asof_only"] = False
    path.write_text(json.dumps(obj),encoding="utf-8")
    with pytest.raises(ValueError, match="CALENDAR_REVIEW"):
        S.freeze_private_future(**args)


def test_pc2_guard_prevents_other_machine_private_snapshot(tmp_path,monkeypatch):
    args=setup(tmp_path,monkeypatch)
    monkeypatch.setenv("COMPUTERNAME","UNAUTHORIZED-PC")
    with pytest.raises(ValueError,match="PC2_CONTEXT"):
        S.freeze_private_future(**args)
