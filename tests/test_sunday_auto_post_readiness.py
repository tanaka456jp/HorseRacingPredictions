"""Sunday publication-readiness: missing data cannot become a fake AI post."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import pandas as pd
import pytest

from horse_racing_predictions import sunday_auto_post_readiness as gate

AS_OF = datetime.fromisoformat("2026-10-24T18:30:00+09:00")


def _make_bundle(tmp_path: Path, complete=True):
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.cbm").write_bytes(b"synthetic fake, never load directly")
    (model / "manifest.json").write_text('{"fixture":true}', encoding="utf8")
    (tmp_path / "race_history.csv").write_text("race_id,race_date\nP,2026-10-17\n", encoding="utf8")
    (tmp_path / "sunday_entries.csv").write_text("race_id,horse_name\nF,H\n", encoding="utf8")
    ids = [
        f"JRA-20261025-{venue}-{n:02d}"
        for venue in ("TOKYO", "KYOTO", "NIIGATA") for n in range(1, 13)
    ]
    manifest = {
        "raceDate": "2026-10-25",
        "sourceKind": "jra-official-pre-race-card",
        "expectedRaceIds": ids if complete else ids[:-1],
    }
    (tmp_path / "race_manifest.json").write_text(
        json.dumps(manifest), encoding="utf8",
    )
    return tmp_path


def test_bundle_absent_gives_safe_reason_no_provider_attempt(tmp_path):
    result = gate.diagnose_sunday_auto_post(tmp_path / "absent", observed_at=AS_OF)
    assert result["status"] == "BLOCKED"
    assert result["blockers"] == ["LOCAL_BUNDLE_MISSING"]
    assert result["notePostAttempted"] is False
    assert result["providerAccessAttempted"] is False
    assert "modelOutputSha256" not in result


def test_partial_bundle_never_treats_saved_pedigree_as_race_history(tmp_path):
    (tmp_path / "pedigree_snapshot.csv").write_text("BLDN\n", encoding="utf8")
    result = gate.diagnose_sunday_auto_post(tmp_path, observed_at=AS_OF)
    assert "LOCAL_INPUTS_INCOMPLETE" in result["blockers"]
    assert "HISTORY" in result["missingInputRoles"]
    assert "ENTRIES" in result["missingInputRoles"]
    assert result["publicationAuthorized"] is False


def test_empty_35_race_card_refused_before_model_calls(tmp_path, monkeypatch):
    root = _make_bundle(tmp_path, complete=False)
    def called(*_args, **_kw):
        raise AssertionError("model called despite bad manifest")
    monkeypatch.setattr(gate, "load_champion_artifact", called)
    result = gate.diagnose_sunday_auto_post(root, observed_at=AS_OF)
    assert result["blockers"][0] == "REAL_SUNDAY_MODEL_INFERENCE_NOT_VERIFIED"
    assert not result["modelComputed"]


def test_real_model_call_is_not_sufficient_for_publication(tmp_path, monkeypatch):
    root = _make_bundle(tmp_path)
    seen = {"model_called": False, "inputs": False}

    def load_model(_path):
        seen["model_called"] = True
        return object()

    def read_csv(path):
        seen["inputs"] = True
        return pd.DataFrame({"dummy": [1]})

    def private_preview(**kwargs):
        assert len(kwargs["expected_race_ids"]) == 36
        assert kwargs["observed_at"] == AS_OF
        return {
            "raceCount": 36,
            "runnerCount": 386,
            "modelOutputSha256": "a" * 64,
        }

    monkeypatch.setattr(gate, "load_champion_artifact", load_model)
    monkeypatch.setattr(gate, "read_csv_flexible", read_csv)
    monkeypatch.setattr(gate, "private_sunday_ai_preview", private_preview)
    result = gate.diagnose_sunday_auto_post(root, observed_at=AS_OF)
    assert seen["model_called"] is True and seen["inputs"] is True
    assert result["modelComputed"] is True
    assert result["raceCount"] == 36
    assert len(result["modelOutputSha256"]) == 64
    assert result["publicationAuthorized"] is False
    assert result["notePostAttempted"] is False
    assert "INDEPENDENT_OUTSIDER_MODEL_NOT_VERIFIED" in result["blockers"]
    assert "INDEPENDENT_MODEL_PROVENANCE_NOT_VERIFIED" in result["blockers"]


def test_invalid_roster_response_digest_rejected(tmp_path, monkeypatch):
    root = _make_bundle(tmp_path)
    monkeypatch.setattr(gate, "load_champion_artifact", lambda _: object())
    monkeypatch.setattr(gate, "read_csv_flexible", lambda _: pd.DataFrame({"ok":[1]}))
    monkeypatch.setattr(
        gate, "private_sunday_ai_preview",
        lambda **_: {"raceCount": 36, "runnerCount": 999, "modelOutputSha256": "FAKE"},
    )
    result = gate.diagnose_sunday_auto_post(root, observed_at=AS_OF)
    assert result["modelComputed"] is False
    assert result["status"] == "BLOCKED"


def test_manifest_is_complete_unique_each_venue(tmp_path):
    root = _make_bundle(tmp_path)
    ids = gate._read_manifest(root)
    assert len(ids) == 36
    assert len(set(ids)) == 36
    obj = json.loads((root / "race_manifest.json").read_text())
    obj["expectedRaceIds"][1] = obj["expectedRaceIds"][0]
    (root / "race_manifest.json").write_text(json.dumps(obj), encoding="utf8")
    with pytest.raises(ValueError):
        gate._read_manifest(root)


def test_symlink_model_or_path_escape_cannot_open_local_artifact(tmp_path):
    root = _make_bundle(tmp_path)
    path = root / "model" / "model.cbm"
    path.unlink()
    outside = root.parent / "outsider-fake-model.cbm"
    outside.write_bytes(b"not a model")
    try:
        path.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unsupported")
    result = gate.diagnose_sunday_auto_post(root, observed_at=AS_OF)
    assert "LOCAL_INPUTS_INCOMPLETE" in result["blockers"]
    assert result["notePostAttempted"] is False


def test_never_contains_raw_filename_or_horse_name_in_report(tmp_path):
    root = _make_bundle(tmp_path)
    (root / "sunday_entries.csv").write_text(
        "horse_name\n架空馬・絶対に公開禁止\n", encoding="utf8",
    )
    output = gate.diagnose_sunday_auto_post(root, observed_at=AS_OF)
    content = json.dumps(output, ensure_ascii=False)
    assert "架空馬" not in content
    assert "race_history.csv" not in content
    assert "sunday_entries.csv" not in content
    assert "publicationAuthorized" in content


@pytest.mark.parametrize("instant", [
    "2026-10-25T08:00:00+09:00",
    "2026-10-25T16:01:00+09:00",
    "2026-10-24T23:00:00+00:00",
    "2026-10-26T00:01:00+09:00",
])
def test_expired_pre_race_cutoff_blocks_before_model_or_private_data(
    tmp_path, monkeypatch, instant,
):
    root = _make_bundle(tmp_path)
    def forbidden(*_a, **_kw):
        raise AssertionError("No input or model may be loaded after cutoff")
    monkeypatch.setattr(gate, "load_champion_artifact", forbidden)
    monkeypatch.setattr(gate, "read_csv_flexible", forbidden)
    monkeypatch.setattr(gate, "private_sunday_ai_preview", forbidden)
    report = gate.diagnose_sunday_auto_post(
        root, observed_at=datetime.fromisoformat(instant),
    )
    assert report["blockers"] == ["HISTORIC_PRE_RACE_CUTOFF_EXPIRED"]
    assert report["modelComputed"] is False
    assert report["publicationAuthorized"] is False
    assert report["notePostAttempted"] is False


def test_requires_timezone_aware_evidence_timestamp(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        gate.diagnose_sunday_auto_post(
            tmp_path, observed_at=datetime(2026, 10, 24, 18, 30),
        )
