"""Only fabricated fixtures; no live provider requests or local archive reads."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import pytest

from horse_racing_predictions.alternative_source_intake import (
    inspect_alternative_csv,
)
from horse_racing_predictions.pre2025_training_csv_audit import (
    UnsafeTrainingSource,
)

TODAY = date(2026, 10, 29)


def _fixture(tmp_path, *, kind="history", term="2027-12-31"):
    root = tmp_path / "sources"
    root.mkdir()
    source = root / "fictional.csv"
    if kind == "history":
        content = (
            "race_id,race_date,horse_name,finish_position\n"
            "MOCKA,2020-04-01,FICTIONAL_1,1\n"
            "MOCKA,2020-04-01,FICTIONAL_2,2\n"
        )
    else:
        content = (
            "race_id,race_date,horse_name,"
            "win_return_per_100_yen,place_return_per_100_yen\n"
            "MOCKA,2020-04-01,FICTIONAL_1,350,150\n"
            "MOCKA,2020-04-01,FICTIONAL_2,0,120\n"
        )
    source.write_text(content, encoding="utf-8")
    payload = {
        "schema_version": 1,
        "kind": kind,
        "provider_id": "fictional-rightsholder",
        "source_category": "rightsholder_licensed",
        "rights_holder": "Fictional Test Data Creator",
        "acquisition_method": "directly supplied synthetic files",
        "rights_evidence_ref": "local-fixture-only-synthetic",
        "rights_scope": "private_noncommercial_research",
        "local_ml_permitted": True,
        "retention_permitted": True,
        "contract_valid_through": term,
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
    }
    manifest = root / "private_manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return source, manifest, payload


@pytest.mark.parametrize("kind", ["history", "settlement"])
def test_offline_alternative_source_intake_is_only_pending_review(tmp_path, kind):
    source, manifest, payload = _fixture(tmp_path, kind=kind)
    result = inspect_alternative_csv(source, manifest, kind=kind, today=TODAY)
    assert result.status == "PRIVATE_OPERATOR_REVIEW_ONLY_NOT_TRAINING_APPROVAL"
    assert result.kind == kind
    assert result.total_rows == 2
    assert result.min_year == result.max_year == 2020
    assert result.operator_claims_private_ml_rights is True
    assert not result.actual_source_rights_independently_verified
    assert not result.approved_for_model_training
    assert not result.web_data_downloaded
    assert not result.published_to_note
    assert "FICTIONAL_1" not in repr(result)
    assert str(source) not in repr(result)
    assert payload["source_sha256"] not in repr(result)


def test_rejects_expired_trial_permissions(tmp_path):
    src, manifest, payload = _fixture(tmp_path, term="2026-10-28")
    with pytest.raises(UnsafeTrainingSource, match="SOURCE_RIGHTS_EXPIRED"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


@pytest.mark.parametrize("name", ["local_ml_permitted", "retention_permitted"])
def test_unattested_source_rights_blocked(tmp_path, name):
    src, manifest, payload = _fixture(tmp_path)
    payload[name] = False
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(UnsafeTrainingSource, match="PRIVATE_RESEARCH_RIGHTS_NOT_ATTESTED"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


def test_source_fingerprint_mismatch_rejected(tmp_path):
    src, manifest, payload = _fixture(tmp_path)
    src.write_text(src.read_text() + "MOCKB,2021-01-01,TEST,1\n")
    with pytest.raises(UnsafeTrainingSource, match="ALTERNATIVE_SOURCE_DIGEST_MISMATCH"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


def test_protected_2025_holdout_is_not_read_for_training(tmp_path):
    src, manifest, payload = _fixture(tmp_path)
    src.write_text(src.read_text() + "MOCKB,2025-01-01,SECRET,1\n")
    payload["source_sha256"] = sha256(src.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_HOLDOUT_IN_SOURCE"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


def test_known_jvlink_provider_is_not_an_alternative_route(tmp_path):
    src, manifest, payload = _fixture(tmp_path)
    payload["provider_id"] = "jra-van-jv-link"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(UnsafeTrainingSource, match="KNOWN_PROVIDER_REQUIRES_SEPARATE_REVIEW"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


def test_free_to_view_not_a_license_for_perpetual_ml(tmp_path):
    src, manifest, payload = _fixture(tmp_path, term="perpetual")
    with pytest.raises(UnsafeTrainingSource, match="PERPETUAL_LICENSE_UNVERIFIED"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


def test_parent_staging_not_training_authorization(tmp_path):
    src, manifest, payload = _fixture(tmp_path)
    (src.parent / "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING").write_text("NO")
    with pytest.raises(UnsafeTrainingSource, match="ALTERNATIVE_SOURCE_PATH_INVALID"):
        inspect_alternative_csv(src, manifest, kind="history", today=TODAY)


def test_payout_duplicate_race_horse_rejected(tmp_path):
    src, manifest, payload = _fixture(tmp_path, kind="settlement")
    with src.open("a", encoding="utf-8") as f:
        f.write("MOCKA,2020-04-01,FICTIONAL_1,350,150\n")
    payload["source_sha256"] = sha256(src.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(UnsafeTrainingSource, match="DUPLICATE_SETTLEMENT_ROW"):
        inspect_alternative_csv(src, manifest, kind="settlement", today=TODAY)


def test_settlement_invalid_payout_and_date_conflict(tmp_path):
    src, manifest, payload = _fixture(tmp_path, kind="settlement")
    text = src.read_text().replace(
        "MOCKA,2020-04-01,FICTIONAL_2,0,120",
        "MOCKA,2020-04-02,FICTIONAL_2,0,120",
    )
    src.write_text(text)
    payload["source_sha256"] = sha256(src.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(UnsafeTrainingSource, match="SETTLEMENT_RACE_DATE_CONFLICT"):
        inspect_alternative_csv(src, manifest, kind="settlement", today=TODAY)


def test_no_network_source_discovery_is_performed(tmp_path, monkeypatch):
    # The intake receives explicit absolute local paths, never a URL.
    src, manifest, _ = _fixture(tmp_path)
    assert inspect_alternative_csv(src, manifest, kind="history", today=TODAY).total_rows == 2
    with pytest.raises(UnsafeTrainingSource, match="ALTERNATIVE_SOURCE_PATH_INVALID"):
        inspect_alternative_csv("https://example.com/races.csv", manifest, kind="history", today=TODAY)
