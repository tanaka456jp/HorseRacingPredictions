"""Read-only CatBoost artifact integrity and model chronology regressions.

Mock binary only exercises byte-level integrity. It does NOT prove a real
CatBoost model could load or yield calibrated odds-free predictions.
"""
from hashlib import sha256
import json

from horse_racing_predictions.friday_model_artifact_audit import (
    inspect_frozen_model_bytes,
)

ISSUE = "2026-10-23"
MODEL_ID = "champion-v7"
FREEZE = "2026-10-22T09:00:00+09:00"


def _fixture(tmp_path):
    directory = tmp_path / "champion"
    directory.mkdir()
    raw = b"FAKE_CATBOOST_BYTES_ONLY_FOR_CHECKSUM_TEST"
    (directory / "model.cbm").write_bytes(raw)
    native = {
        "model_version": MODEL_ID,
        "experiment_id": "v7-catboost-recent-form",
        "model_kind": "catboost",
        "feature_columns": ["distance_m", "horse_recent_win_rate_3"],
        "categorical_columns": [],
        "train_start": "2017-01-01",
        "train_end": "2021-07-31",
        "source_id": "approved-research-test-source",
        "validation_brier": 0.06,
        "validation_log_loss": 0.2,
        "validation_research_roi": -0.019,
        "created_at": "2026-10-21T13:00:00+09:00",
    }
    (directory / "manifest.json").write_text(
        json.dumps(native), encoding="utf-8")
    candidate = {
        "schemaVersion": 1,
        "modelId": MODEL_ID,
        "featureNames": list(native["feature_columns"]),
        "frozenAt": FREEZE,
        "artifactSha256": sha256(raw).hexdigest(),
        "oddsFreeClaim": True,
    }
    return directory, native, candidate


def _check(directory, candidate, forecast=None):
    return inspect_frozen_model_bytes(
        artifact_directory=directory, candidate_model=candidate,
        issue_date=ISSUE, forecast=forecast,
    )


def test_matching_bytes_and_manifest_still_not_approval(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    result = _check(directory, candidate)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["modelBytesSha256"] == candidate["artifactSha256"]
    assert result["featureCount"] == 2
    assert result["trainEnd"] == "2021-07-31"
    assert result["trainGapDays"] > 1000
    assert result["trainingSampleSelectionMarketExposureNeedsReview"] is True
    assert "publicationAuthorized" not in result


def test_tampered_model_binary_never_passes(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    (directory / "model.cbm").write_bytes(b"ALTERED")
    result = _check(directory, candidate)
    assert result["status"] == "REJECTED"
    assert "SHA-256 mismatch" in result["reason"]


def test_candidate_model_identity_does_not_override_native_manifest(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    candidate["modelId"] = "made-up-model"
    assert _check(directory, candidate)["status"] == "REJECTED"


def test_embedded_market_feature_rejected_even_when_candidate_claims_free(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    native["feature_columns"] = ["distance_m", "win_odds"]
    candidate["featureNames"] = list(native["feature_columns"])
    (directory / "manifest.json").write_text(
        json.dumps(native), encoding="utf-8")
    result = _check(directory, candidate)
    assert result["status"] == "REJECTED"
    assert "market/popularity" in result["reason"]


def test_candidate_features_must_equal_native_sequence(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    candidate["featureNames"].reverse()
    assert "differ" in _check(directory, candidate)["reason"]


def test_created_later_than_frozen_is_rejected(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    native["created_at"] = "2026-10-23T16:00:00+09:00"
    (directory / "manifest.json").write_text(json.dumps(native), encoding="utf-8")
    assert _check(directory, candidate)["status"] == "REJECTED"


def test_protected_2025_2026_final_holdout_is_rejected_even_before_issue(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    for forbidden in ("2025-01-01", "2026-06-01"):
        native["train_end"] = forbidden
        (directory / "manifest.json").write_text(
            json.dumps(native), encoding="utf-8"
        )
        result = _check(directory, candidate)
        assert result["status"] == "REJECTED"
        assert "protected final holdout" in result["reason"]


def test_training_start_after_end_rejected(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    native["train_start"] = "2024-01-01"
    (directory / "manifest.json").write_text(
        json.dumps(native), encoding="utf-8"
    )
    assert "training start" in _check(directory, candidate)["reason"]


def test_fullwidth_market_columns_rejected(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    native["feature_columns"] = ["distance_m", "ｏｄｄｓ"]
    candidate["featureNames"] = list(native["feature_columns"])
    (directory / "manifest.json").write_text(
        json.dumps(native), encoding="utf-8"
    )
    assert "market/popularity" in _check(directory, candidate)["reason"]


def test_model_creation_before_training_end_rejected(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    native["train_end"] = "2024-12-31"
    native["created_at"] = "2024-01-01T09:00:00+09:00"
    (directory / "manifest.json").write_text(
        json.dumps(native), encoding="utf-8"
    )
    assert "creation predates" in _check(directory, candidate)["reason"]


def test_post_issue_model_training_rejected(tmp_path):
    directory, native, candidate = _fixture(tmp_path)
    native["train_end"] = "2026-10-24"
    (directory / "manifest.json").write_text(json.dumps(native), encoding="utf-8")
    assert _check(directory, candidate)["status"] == "REJECTED"


def test_forecast_model_identity_and_freeze_must_match(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    forecast = {"model_id": MODEL_ID, "model_frozen_at": FREEZE}
    assert _check(directory, candidate, forecast)["status"] == "REVIEW_REQUIRED"
    forecast["model_frozen_at"] = "2026-10-21T13:00:00+09:00"
    assert _check(directory, candidate, forecast)["status"] == "REJECTED"


def test_invalid_manifest_or_symlink_block(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    manifest = directory / "manifest.json"
    manifest.write_text('{"x":1,"x":2}', encoding="utf-8")
    assert _check(directory, candidate)["status"] == "REJECTED"
    try:
        link = tmp_path / "alias"
        link.symlink_to(directory, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    assert _check(link, candidate)["status"] == "REJECTED"


def test_missing_candidate_or_binary_rejected(tmp_path):
    directory, _, candidate = _fixture(tmp_path)
    assert _check(directory, None)["status"] == "REJECTED"
    (directory / "model.cbm").unlink()
    assert _check(directory, candidate)["status"] == "REJECTED"
