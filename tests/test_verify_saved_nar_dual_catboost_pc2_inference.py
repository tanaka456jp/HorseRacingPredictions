"""Use only fake in-memory native models; PC2 workflow tests real binaries."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest

from horse_racing_predictions.modeling import CatBoostProbabilityModel
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_saved_nar_dual_catboost_pc2_inference as M  # noqa: E402


class FakeNative:
    def __init__(self, label):
        self.label = label

    def predict(self, frame, prediction_type):
        assert prediction_type == "RawFormulaVal"
        return frame[self.label].to_numpy(dtype=float)


def fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    a = CatBoostProbabilityModel(feature_columns=list(M._FEATURES))
    b = CatBoostProbabilityModel(feature_columns=list(M._FEATURES))
    a.model, b.model = FakeNative("past_win_rate"), FakeNative("past_top3_rate")
    monkeypatch.setattr(M, "load_dual_research_candidate", lambda _: SimpleNamespace(
        winner=a, outsider=b, features=M._FEATURES,
        train_end="2021-12-31",
        digest_by_role={"win.cbm":"a"*64, "outsider.cbm":"b"*64},
    ))


def test_synthetic_model_native_smoke_never_claims_real_forward_result(
    tmp_path, monkeypatch,
):
    fixture(tmp_path, monkeypatch)
    result = M.verify_saved_model(tmp_path)
    assert result["status"].startswith("PRIVATE_REAL_TRAINED_MODELS")
    assert result["fictional_races_scored"] == 1
    assert result["real_future_races_scored"] == 0
    assert result["independent_native_win_and_podium_inference_executed"]
    assert not result["positive_ev_proven"]


def test_model_feature_mismatch_and_wrong_machine_block(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(M, "load_dual_research_candidate", lambda _: SimpleNamespace(
        winner=None, outsider=None, features=("wrong_feature",),
        train_end="2021-12-31", digest_by_role={},
    ))
    with pytest.raises(ValueError, match="SCHEMA_MISMATCH"):
        M.verify_saved_model(tmp_path)
    monkeypatch.setenv("COMPUTERNAME", "WRONG_PC")
    with pytest.raises(ValueError, match="PC2_CONTEXT"):
        M.verify_saved_model(tmp_path)
