"""Offline synthetic future JRA/NAR source/model preflight tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_future_fitted_model_pc2_readiness as M  # noqa: E402

NOW = datetime(2026, 11, 23, 10, tzinfo=timezone.utc)


def setup_model(root, series):
    folder = root / M.MODEL_LOCATIONS[series]
    folder.mkdir(parents=True)
    hashes = {}
    for name in ("win.cbm", "outsider.cbm"):
        data = (name + "FICTIONAL_NATIVE_BINARY").encode()
        (folder / name).write_bytes(data)
        hashes[name] = sha256(data).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "artifactKind": "dual-catboost-oddsfree-research-candidate",
        "status": "RESEARCH_NOT_APPROVED_FOR_PUBLICATION",
        "publicationAuthorized": False,
        "sourceRightsIndependentlyVerified": False,
        "independentOutsiderModelVerified": False,
        "trainEnd": "2021-12-31",
        "featureColumns": ["past_starts", "past_top3_rate"],
        "artifactSha256": hashes,
    }
    (folder / "candidate_manifest.json").write_text(json.dumps(manifest))
    return folder


def setup_future(root, series, *, missing=False, contaminated=False):
    directory = root / "forward-model-inputs"
    directory.mkdir(exist_ok=True)
    rid = ("JRA-20261124-KYOTO-01" if series == "JRA"
           else "NAR:20261124:架空場:01")
    manifest = {
        "schema": "HorseRacing.PrivateFutureCalendar.v1",
        "jurisdiction": series, "race_day_jst": "2026-11-24",
        "source_asof_utc": NOW.isoformat(),
        "scheduled_off_utc": {
            rid: (NOW + timedelta(hours=10)).isoformat()},
        "runner_count_by_race": {rid: 4},
        "operator_reviewed_asof_only": True,
        "operator_reviewed_complete_roster": True,
    }
    prefix = directory / f"20261124_{series}_future"
    (directory / (prefix.name + "_calendar.json")).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    import csv
    columns = ["race_id", "horse_id", "past_starts", "past_top3_rate"]
    if contaminated:
        columns += ["finish_position"]
    with (directory / (prefix.name + "_features.csv")).open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for i in range(1, 4 if missing else 5):
            record = {"race_id": rid, "horse_id": str(i),
                      "past_starts": str(i), "past_top3_rate": str(i / 4)}
            if contaminated:
                record["finish_position"] = "1"
            writer.writerow(record)


@pytest.mark.parametrize("series", ["JRA", "NAR"])
def test_future_model_and_complete_roster_detection(tmp_path, monkeypatch, series):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    assert M.audit(tmp_path, NOW)["status"].startswith("HOLD")
    setup_model(tmp_path, series)
    assert M.audit(tmp_path, NOW)[series + "_model_checksums_verified"] is True
    assert M.audit(tmp_path, NOW)[series + "_complete_future_cards"] == 0
    setup_future(tmp_path, series)
    result = M.audit(tmp_path, NOW)
    assert result[series + "_complete_future_cards"] == 1
    assert result["status"] == "FUTURE_INPUTS_READY_PRIVATE_INFERENCE_PENDING"
    assert result["provider_requests"] == 0
    assert result["source_model_or_horse_data_uploaded"] is False
    assert result["real_forward_roi_measured"] is False


def test_incomplete_roster_and_leaking_result_are_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    setup_model(tmp_path, "NAR")
    setup_future(tmp_path, "NAR", missing=True)
    assert M.audit(tmp_path, NOW)["NAR_complete_future_cards"] == 0
    setup_future(tmp_path, "NAR", contaminated=True)
    assert M.audit(tmp_path, NOW)["NAR_complete_future_cards"] == 0


def test_model_tampering_or_wrong_machine_holds(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    model = setup_model(tmp_path, "JRA")
    setup_future(tmp_path, "JRA")
    (model / "win.cbm").write_bytes(b"tampered")
    assert M.audit(tmp_path, NOW)["JRA_model_checksums_verified"] is False
    monkeypatch.setenv("COMPUTERNAME", "WRONG-PC")
    assert M.audit(tmp_path, NOW)["status"] == "HOLD_PRIVATE_PC2_CONTEXT_INVALID"
