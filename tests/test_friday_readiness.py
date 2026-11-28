"""Offline readiness: no synthetic forecast or self-attestation permits publishing."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import pytest

from horse_racing_predictions.friday_readiness import (
    FridayAuditError,
    audit_friday_inputs,
)

ISSUE = "2026-10-23"
SOURCE = "2026-10-22T09:00:00+09:00"
RACE = "JRA-20261024-01A"


def _write(folder: Path, name: str, document: dict) -> Path:
    path = folder / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def _forecast():
    factors = [
        {"category": category, "finding": "合成データ・テスト用途",
         "source_url": "https://example.org/fictional",
         "observed_at": SOURCE}
        for category in ("近走内容", "距離適性", "血統")
    ]
    horses = [
        {"name": f"架空馬{i}", "number": i, "strength": float(10-i),
         "upside_score": float(i), "upside_signals": ["近走内容", "距離適性"],
         "factors": deepcopy(factors)}
        for i in range(1, 5)
    ]
    return {
        "issue_date": ISSUE, "generated_at": "2026-10-23T19:00:00+09:00",
        "model_id": "synthetic-sample-not-real-v1",
        "model_frozen_at": "2026-10-21T13:00:00+09:00",
        "input_approved_for_research": True,
        "complete_race_manifest": True,
        "expected_race_ids": [RACE],
        "races": [
            {"race_id": RACE, "title": "仮想1レース",
             "course": "架空芝1600m", "post_at": "2026-10-24T10:00:00+09:00",
             "status": "confirmed", "horses": horses}
        ],
    }


def _rights(provider="independent-free-source", permitted=True):
    return {
        "schemaVersion": 1, "providerId": provider,
        "datasetKind": "historical-form", "publicationPermission": permitted,
        "personalUseOnly": False, "capturedAt": SOURCE,
        "permissionBasisUrl": "https://example.org/terms",
    }


def _manifest(races=None):
    return {
        "schemaVersion": 1, "issueDate": ISSUE, "observedAt": SOURCE,
        "expectedRaceIds": [RACE] if races is None else races,
    }


def _model():
    return {
        "schemaVersion": 1, "modelId": "synthetic-sample-not-real-v1",
        "frozenAt": "2026-10-21T13:00:00+09:00",
        "artifactSha256": "a" * 64, "featureNames": ["recent_form", "pedigree"],
        "oddsFreeClaim": True,
    }


def _files(tmp_path):
    return {
        "forecast_json": _write(tmp_path, "forecast.json", _forecast()),
        "source_rights_json": _write(tmp_path, "rights.json", _rights()),
        "race_manifest_json": _write(tmp_path, "races.json", _manifest()),
        "model_manifest_json": _write(tmp_path, "model.json", _model()),
    }


def test_missing_data_reports_blocked_no_mutation():
    report = audit_friday_inputs(issue_date=ISSUE)
    assert report["status"] == "BLOCKED"
    assert report["publicationAuthorized"] is False
    assert report["independentVerifierSatisfied"] is False
    assert all(item["status"] == "MISSING" for item in report["checks"].values())


def test_all_four_structurally_valid_files_still_not_publication_proof(tmp_path):
    files = _files(tmp_path)
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert report["status"] == "BLOCKED"
    assert report["publicationAuthorized"] is False
    assert report["independentVerifierSatisfied"] is False
    for item in report["checks"].values():
        assert item["status"] == "REVIEW_REQUIRED"
        assert len(item["sha256"]) == 64
    assert report["checks"]["raceManifest"]["raceCount"] == 1
    assert report["checks"]["forecastInput"]["raceCount"] == 1
    assert len(report["checks"]["forecastInput"]["renderSha256"]) == 64
    assert report["checks"]["modelManifest"]["featureCount"] == 2
    assert "架空馬" not in json.dumps(report, ensure_ascii=False)


def test_private_jravan_datalab_cannot_self_authorize(tmp_path):
    files = _files(tmp_path)
    _write(tmp_path, "rights.json", _rights("jra-van-datalab"))
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert report["checks"]["sourceRights"]["status"] == "PROHIBITED"
    assert not report["publicationAuthorized"]


def test_injected_free_permission_not_accepted(tmp_path):
    files = _files(tmp_path)
    _write(tmp_path, "rights.json", _rights(permitted=False))
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert report["checks"]["sourceRights"]["status"] == "REJECTED"


def test_differing_race_ids_rejected_without_dropping_races(tmp_path):
    files = _files(tmp_path)
    _write(tmp_path, "races.json", _manifest(["JRA-20261024-02B"]))
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert report["checks"]["raceManifest"]["status"] == "REJECTED"


@pytest.mark.parametrize("feature", ["odds", "market_rank", "人気順位", "payout", "オッズ履歴"])
def test_market_features_are_rejected_even_with_odds_free_claim(tmp_path, feature):
    files = _files(tmp_path)
    model = _model()
    model["featureNames"].append(feature)
    _write(tmp_path, "model.json", model)
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert report["checks"]["modelManifest"]["status"] == "REJECTED"


def test_fabricated_odd_or_future_values_fail_renderer_validation(tmp_path):
    files = _files(tmp_path)
    forecast = _forecast()
    forecast["races"][0]["horses"][0]["odds"] = 4.5
    _write(tmp_path, "forecast.json", forecast)
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert report["checks"]["forecastInput"]["status"] == "REJECTED"
    assert report["publicationAuthorized"] is False


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "dupe.json"
    path.write_text('{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8")
    report = audit_friday_inputs(issue_date=ISSUE, source_rights_json=path)
    assert report["checks"]["sourceRights"]["status"] == "REJECTED"
    assert report["publicationAuthorized"] is False


def test_symlink_inputs_are_refused(tmp_path):
    real = _write(tmp_path, "real.json", _rights())
    link = tmp_path / "alias.json"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not support symlinks")
    report = audit_friday_inputs(issue_date=ISSUE, source_rights_json=link)
    assert report["checks"]["sourceRights"]["status"] == "REJECTED"


@pytest.mark.parametrize("issue", ["2026-10-24", "2026-02-30", "20261023", "2026-10-22"])
def test_requires_actual_friday(issue):
    with pytest.raises(FridayAuditError):
        audit_friday_inputs(issue_date=issue)


def test_future_or_tampered_model_manifest_fails(tmp_path):
    files = _files(tmp_path)
    model = _model()
    model["frozenAt"] = "2026-10-24T09:00:00+09:00"
    _write(tmp_path, "model.json", model)
    result = audit_friday_inputs(issue_date=ISSUE, **files)
    assert result["checks"]["modelManifest"]["status"] == "REJECTED"


def test_no_secret_raw_values_in_report(tmp_path):
    files = _files(tmp_path)
    rights = _rights()
    rights["secretPrivateToken"] = "dont_print_this"
    _write(tmp_path, "rights.json", rights)
    report = audit_friday_inputs(issue_date=ISSUE, **files)
    assert "dont_print_this" not in json.dumps(report)
