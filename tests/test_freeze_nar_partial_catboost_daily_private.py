"""No real horse, source download, nor licensed data: synthetic NAR race ZIP."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import freeze_nar_partial_catboost_daily_private as M  # noqa: E402
from test_nar_official_daily_preoff import fictional_daily_zip  # noqa: E402
from horse_racing_predictions.modeling import CatBoostProbabilityModel

DAY = date(2026, 11, 10)
OBS = datetime(2026, 11, 10, 0, tzinfo=timezone.utc)
GEN = OBS + timedelta(minutes=4)


class FakeNative:
    def __init__(self, feature):
        self.feature = feature

    def predict(self, frame, prediction_type):
        assert prediction_type == "RawFormulaVal"
        return frame[self.feature].to_numpy(dtype=float)


def fake_model():
    features = ["past_starts", "past_win_rate", "past_top3_rate",
                "past_mean_finish", "days_since_last_start"]
    a = CatBoostProbabilityModel(feature_columns=features)
    b = CatBoostProbabilityModel(feature_columns=features)
    a.model = FakeNative("past_win_rate")
    b.model = FakeNative("past_top3_rate")
    return SimpleNamespace(
        winner=a, outsider=b, features=tuple(features),
        train_end="2021-12-31",
        digest_by_role={"win.cbm":"a"*64,"outsider.cbm":"b"*64},
    )


def test_official_career_three_of_five_are_exact_unavailable_are_nan():
    frame, offs, counts = M.partial_preoff_features(
        fictional_daily_zip(), race_day=DAY, captured_utc=OBS,
    )
    assert len(frame) == 8
    assert len(offs) == 2
    assert counts["observed_feature_count"] == 3
    assert counts["unavailable_feature_count"] == 2
    r = frame.loc[frame.horse_id.eq("1")].iloc[0]
    assert r["past_starts"] == 8
    assert r["past_win_rate"] == 2/8
    assert r["past_top3_rate"] == 4/8
    assert frame["past_mean_finish"].isna().all()
    assert frame["days_since_last_start"].isna().all()


def test_actual_wrapper_runs_fitted_model_on_complete_preoff_zip():
    frozen, counts = M.freeze_partial_from_official_source(
        fictional_daily_zip(), day=DAY, observed_utc=OBS,
        generated_utc=GEN, loaded=fake_model(),
    )
    assert len(frozen.races) == counts["races"] == 2
    assert len(frozen.races[0].top3) == 3
    assert frozen.races[0].outsider not in frozen.races[0].top3
    assert frozen.positive_expected_value_proven is False
    assert frozen.verified_external_timestamp is False


def test_partial_source_rejects_results_or_after_first_off():
    with pytest.raises(Exception):
        M.partial_preoff_features(
            fictional_daily_zip(result=True), race_day=DAY,
            captured_utc=OBS,
        )
    with pytest.raises(Exception):
        M.freeze_partial_from_official_source(
            fictional_daily_zip(), day=DAY, observed_utc=OBS,
            generated_utc=datetime(2026, 11, 10, 2, 31, tzinfo=timezone.utc),
            loaded=fake_model(),
        )


def test_live_private_snapshot_is_exclusive_and_no_source_upload(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    candidate = tmp_path / "nar-prospective-captures"
    candidate.mkdir()
    data = fictional_daily_zip()
    source = candidate / "20261110_20261110T000000Z_race.zip"
    source.write_bytes(data)
    salt = bytes(range(32))
    provenance = {
        "schema": "NAR.OfficialDailyPreoffCapture.v1",
        "salt_hex_PRIVATE": salt.hex(),
        "salted_zip_sha256_PRIVATE": sha256(
            b"NAR_OFFICIAL_DAILY_RACE_V1\x00" + salt + data
        ).hexdigest(),
        "host_captured_utc": OBS.isoformat(),
    }
    (candidate / source.name.replace("_race.zip", "_private_provenance.json")).write_text(
        json.dumps(provenance), encoding="utf-8",
    )
    monkeypatch.setattr(M, "load_nar_private_dual_candidate",
                        lambda _: fake_model())
    result = M.freeze_private_from_saved_daily(
        tmp_path, generated_utc=GEN,
    )
    assert result["real_preoff_source_races"] == 2
    assert result["available_model_features"] == 3
    assert result["unavailable_model_features"] == 2
    assert result["race_day_jst"] == "2026-11-10"
    assert result["earliest_off_utc"] == "2026-11-10T02:35:00Z"
    assert result["source_observed_at_utc"] == "2026-11-10T00:00:00Z"
    assert result["real_outcome_hits_measured"] is False
    frozen = candidate / "20261110_NAR_partial3of5_dual_catboost_PRIVATE.json"
    original = json.loads(frozen.read_text(encoding="utf-8"))
    assert original["source_feature_mode_PRIVATE"].endswith("RESEARCH_ABLATION")
    assert original["model_missing_features_do_not_equal_full_feature_model"]
    initial_bytes = frozen.read_bytes()
    again = M.freeze_private_from_saved_daily(
        tmp_path, generated_utc=GEN + timedelta(minutes=1),
    )
    assert again["status"] == "PRIVATE_EXISTING_PREOFF_CATBOOST_COMMITMENT_VERIFIED"
    assert again["existing_private_forecast_reused"] is True
    assert again["blinded_digest"] == result["blinded_digest"]
    assert frozen.read_bytes() == initial_bytes


def test_existing_frozen_source_tamper_fails_instead_of_regenerating(tmp_path,monkeypatch):
    monkeypatch.setenv("COMPUTERNAME","DESKTOP-MVV1FD4")
    folder=tmp_path / "nar-prospective-captures"
    folder.mkdir()
    blob=fictional_daily_zip()
    original=folder / "20261110_20261110T000000Z_race.zip"
    original.write_bytes(blob)
    salt=bytes(range(32))
    (folder / original.name.replace("_race.zip","_private_provenance.json")).write_text(
        json.dumps({
            "schema":"NAR.OfficialDailyPreoffCapture.v1",
            "salt_hex_PRIVATE":salt.hex(),
            "salted_zip_sha256_PRIVATE":sha256(
                b"NAR_OFFICIAL_DAILY_RACE_V1\x00"+salt+blob
            ).hexdigest(),
            "host_captured_utc":OBS.isoformat(),
        }),encoding="utf-8"
    )
    monkeypatch.setattr(M,"load_nar_private_dual_candidate",
                        lambda _: fake_model())
    M.freeze_private_from_saved_daily(tmp_path,generated_utc=GEN)
    frozen=folder / "20261110_NAR_partial3of5_dual_catboost_PRIVATE.json"
    old=json.loads(frozen.read_text(encoding="utf-8"))
    old["frozen_shadow_PRIVATE"]["races"][0]["top3"][0]="999"
    frozen.write_text(json.dumps(old,ensure_ascii=False),encoding="utf-8")
    with pytest.raises(ValueError, match="COMMITMENT"):
        M.freeze_private_from_saved_daily(
            tmp_path, generated_utc=GEN+timedelta(minutes=1)
        )


def test_staged_manual_zip_flows_into_model_freeze(tmp_path, monkeypatch):
    import import_nar_manual_daily_race_offline as importer
    monkeypatch.setenv("COMPUTERNAME","DESKTOP-MVV1FD4")
    monkeypatch.setattr(importer,"_now_utc",lambda: OBS)
    monkeypatch.setattr(M,"load_nar_private_dual_candidate",lambda _: fake_model())
    folder=tmp_path/"nar-prospective-captures"
    inbox=folder/"manual-race-inbox"
    inbox.mkdir(parents=True)
    original=inbox/f"20261110_{int(OBS.timestamp())}_race.zip"
    original_bytes=fictional_daily_zip()
    original.write_bytes(original_bytes)
    assert M.prepare_manual_source_if_needed(tmp_path,now=OBS) is True
    out=M.freeze_private_from_saved_daily(tmp_path,generated_utc=GEN)
    assert out["real_preoff_source_races"]==2
    assert out["real_preoff_source_runners"]==8
    assert M.prepare_manual_source_if_needed(tmp_path,now=GEN) is False
    assert original.read_bytes()==original_bytes
    again=M.freeze_private_from_saved_daily(tmp_path,generated_utc=GEN)
    assert again["blinded_digest"]==out["blinded_digest"]


def test_manual_inbox_ambiguity_blocks_without_archiving(tmp_path,monkeypatch):
    monkeypatch.setenv("COMPUTERNAME","DESKTOP-MVV1FD4")
    folder=tmp_path/"nar-prospective-captures"
    inbox=folder/"manual-race-inbox"
    inbox.mkdir(parents=True)
    for offset in (0,1):
        (inbox/f"20261110_{int(OBS.timestamp())+offset}_race.zip").write_bytes(
            fictional_daily_zip())
    with pytest.raises(ValueError,match="AMBIGUOUS"):
        M.prepare_manual_source_if_needed(tmp_path,now=OBS)
    assert not list(folder.glob("20261110_????????T??????Z_race.zip"))
