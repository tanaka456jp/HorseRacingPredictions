"""Synthetic-only future Sunday card validation and no-post regression."""
from datetime import datetime, timedelta
import json

import pandas as pd
import pytest

from horse_racing_predictions import future_sunday_readiness as gate


FRI = datetime.fromisoformat("2026-10-30T19:00:00+09:00")
TARGET = "2026-11-01"


def _bundle(tmp_path, venues=("TOKYO", "KYOTO")):
    (tmp_path / "model").mkdir()
    (tmp_path / "model" / "manifest.json").write_text(
        '{"synthetic":true}', encoding="utf8"
    )
    (tmp_path / "model" / "model.cbm").write_bytes(b"fake model")
    (tmp_path / "race_history.csv").write_text(
        "race_id,race_date\nFAKE,2026-10-24\n", encoding="utf8"
    )
    (tmp_path / "sunday_entries.csv").write_text(
        "race_id,horse_name\nFAKE,架空馬\n", encoding="utf8"
    )
    ids = [
        f"JRA-20261101-{venue}-{n:02d}"
        for venue in venues for n in range(1, 13)
    ]
    (tmp_path / "race_manifest.json").write_text(json.dumps({
        "raceDate": TARGET, "sourceKind": "jra-official-pre-race-card",
        "expectedRaceIds": ids,
    }), encoding="utf8")
    return ids


def test_real_next_sunday_has_two_venues_and_24_id_contract(tmp_path):
    ids = _bundle(tmp_path)
    assert len(ids) == 24
    assert gate._parse_local_manifest(tmp_path, TARGET) == tuple(ids)


@pytest.mark.parametrize("venues", [
    ("TOKYO",), ("TOKYO", "KYOTO"), ("TOKYO", "KYOTO", "NIIGATA"),
])
def test_accepts_declared_complete_12_24_36_official_card_shapes(tmp_path, venues):
    ids = _bundle(tmp_path, venues=venues)
    assert len(gate._parse_local_manifest(tmp_path, TARGET)) == len(ids)


def test_model_preview_on_24_races_still_cannot_enable_note(tmp_path, monkeypatch):
    _bundle(tmp_path)
    monkeypatch.setattr(gate, "load_champion_artifact", lambda _: object())
    monkeypatch.setattr(
        gate, "read_csv_flexible", lambda _: pd.DataFrame({"dummy": [1, 2, 3]})
    )
    seen = []
    def mock_preview(**kw):
        seen.append(kw["expected_race_ids"])
        assert kw["race_date"] == TARGET
        return {
            "raceCount": 24, "runnerCount": 3,
            "modelOutputSha256": "a" * 64,
        }
    monkeypatch.setattr(gate, "private_sunday_ai_preview", mock_preview)
    result = gate.diagnose_future_sunday_bundle(
        tmp_path, race_date=TARGET, observed_at=FRI
    )
    assert len(seen) == 1 and len(seen[0]) == 24
    assert result["modelComputed"] is True
    assert result["raceCount"] == 24
    assert result["status"] == "BLOCKED"
    assert result["publicationAuthorized"] is False
    assert result["sourceRightsIndependentlyVerified"] is False
    assert result["independentOutsiderModelVerified"] is False


def test_late_sunday_or_utc_equivalent_blocks_before_any_io(
    tmp_path, monkeypatch,
):
    _bundle(tmp_path)
    def fail(*a, **k):
        raise AssertionError("No private reads after race cutoff")
    monkeypatch.setattr(gate, "read_csv_flexible", fail)
    monkeypatch.setattr(gate, "load_champion_artifact", fail)
    monkeypatch.setattr(gate, "private_sunday_ai_preview", fail)
    for time in (
        "2026-11-01T08:00:00+09:00",
        "2026-10-31T23:00:00+00:00",
        "2026-11-01T16:01:00+09:00",
        "2026-11-02T00:00:00+09:00",
        "2026-10-28T23:59:00+09:00",
    ):
        result = gate.diagnose_future_sunday_bundle(
            tmp_path, race_date=TARGET,
            observed_at=datetime.fromisoformat(time),
        )
        expected = (
            "PRE_RACE_WINDOW_NOT_YET_OPEN"
            if datetime.fromisoformat(time).astimezone(gate.JST).date()
            < datetime.fromisoformat(TARGET).date() - timedelta(days=2)
            else "PRE_RACE_WINDOW_EXPIRED"
        )
        assert result["blockers"] == [expected]
        assert result["modelComputed"] is False
        assert result["publicationAuthorized"] is False


def test_before_friday_reports_missing_input_roles_without_opening_data(
    tmp_path, monkeypatch,
):
    def forbidden(*a, **k):
        raise AssertionError("Early metadata inspection must not load data/model")
    monkeypatch.setattr(gate, "read_csv_flexible", forbidden)
    monkeypatch.setattr(gate, "load_champion_artifact", forbidden)
    result = gate.diagnose_future_sunday_bundle(
        tmp_path / "not-yet-staged",
        race_date=TARGET,
        observed_at=datetime.fromisoformat("2026-10-25T16:00:00+09:00"),
    )
    assert result["blockers"] == ["PRE_RACE_WINDOW_NOT_YET_OPEN"]
    assert result["localCandidateBundlePresent"] is False
    assert result["missingInputRoles"] == [
        "ENTRIES", "HISTORY", "MODEL", "RACE_MANIFEST"
    ]
    assert result["modelComputed"] is False
    assert result["publicationAuthorized"] is False


def test_missing_bundle_blocked_and_no_provider_calls(tmp_path, monkeypatch):
    def fail(*a, **k):
        raise AssertionError("No inference without valid inputs")
    monkeypatch.setattr(gate, "load_champion_artifact", fail)
    report = gate.diagnose_future_sunday_bundle(
        tmp_path / "missing", race_date=TARGET, observed_at=FRI,
    )
    assert report["blockers"] == ["LOCAL_BUNDLE_MISSING"]
    assert report["providerAccessAttempted"] is False
    assert report["usageKeyRead"] is False
    assert report["notePostAttempted"] is False
    assert report["rawDataUploaded"] is False


def test_declared_card_must_be_complete_unique_and_current(tmp_path):
    ids = _bundle(tmp_path)
    path = tmp_path / "race_manifest.json"
    for changed in (
        ids[:-1],
        ids[:1] + ids[:1] + ids[2:],
        [x.replace("20261101", "20261025") for x in ids],
        [x.replace("-TOKYO-", "-INVALID-") for x in ids],
    ):
        path.write_text(json.dumps({
            "raceDate": TARGET, "sourceKind": "jra-official-pre-race-card",
            "expectedRaceIds": changed,
        }), encoding="utf8")
        with pytest.raises(ValueError):
            gate._parse_local_manifest(tmp_path, TARGET)


def test_fake_market_and_unverified_source_cannot_pass_by_name(tmp_path):
    _bundle(tmp_path)
    result = gate.diagnose_future_sunday_bundle(
        tmp_path, race_date=TARGET, observed_at=FRI,
    )
    assert result["status"] == "BLOCKED"
    assert result["publicationAuthorized"] is False
    assert result["modelComputed"] is False


def test_rejects_non_sunday_and_naive_timestamp(tmp_path):
    with pytest.raises(ValueError, match="Sunday"):
        gate.diagnose_future_sunday_bundle(
            tmp_path, race_date="2026-10-31", observed_at=FRI,
        )
    with pytest.raises(ValueError, match="timezone"):
        gate.diagnose_future_sunday_bundle(
            tmp_path, race_date=TARGET, observed_at=datetime(2026, 10, 30),
        )


def test_dual_real_model_detection_path_is_still_publication_blocked(
    tmp_path, monkeypatch,
):
    _bundle(tmp_path)
    model_dir = tmp_path / "model"
    (model_dir / "candidate_manifest.json").write_text(
        '{"synthetic":true}', encoding="utf8",
    )
    (model_dir / "win.cbm").write_bytes(b"fake-win")
    (model_dir / "outsider.cbm").write_bytes(b"fake-outsider")
    from horse_racing_predictions import dual_candidate_private_preview as dual
    monkeypatch.setattr(dual, "load_dual_research_candidate", lambda _: object())
    monkeypatch.setattr(
        gate, "read_csv_flexible", lambda _: pd.DataFrame({"fake": [1]}),
    )
    received = []

    def private_preview(*args, **kwargs):
        received.append(kwargs["expected_race_ids"])
        return {
            "raceCount": 24, "runnerCount": 1,
            "winModelOutputSha256": "a" * 64,
            "outsiderSelectionSha256": "b" * 64,
            "bothActualModelsExecuted": True,
        }

    monkeypatch.setattr(dual, "private_dual_sunday_preview", private_preview)
    report = gate.diagnose_future_sunday_bundle(
        tmp_path, race_date=TARGET, observed_at=FRI, model_mode="dual",
    )
    assert len(received) == 1 and len(received[0]) == 24
    assert report["modelComputed"] is True
    assert report["bothActualModelsExecuted"] is True
    assert report["modelOutputSha256"] == "a" * 64
    assert report["outsiderSelectionSha256"] == "b" * 64
    assert report["status"] == "BLOCKED"
    assert report["independentOutsiderModelVerified"] is False
    assert report["publicationAuthorized"] is False
    assert report["notePostAttempted"] is False


def test_incomplete_dual_model_must_not_be_treated_as_single_model(tmp_path):
    _bundle(tmp_path)
    (tmp_path / "model" / "candidate_manifest.json").write_text(
        '{"synthetic":true}', encoding="utf8",
    )
    report = gate.diagnose_future_sunday_bundle(
        tmp_path, race_date=TARGET, observed_at=FRI, model_mode="dual",
    )
    assert report["blockers"] == ["LOCAL_INPUTS_INCOMPLETE"]
    assert report["missingInputRoles"] == ["MODEL"]
    assert report["modelComputed"] is False
    assert report["publicationAuthorized"] is False


def test_after_start_does_not_load_dual_private_artifact(tmp_path, monkeypatch):
    _bundle(tmp_path)
    from horse_racing_predictions import dual_candidate_private_preview as dual
    def forbidden(*_a, **_kw):
        raise AssertionError("expired Sunday cannot open CBM files")
    monkeypatch.setattr(dual, "load_dual_research_candidate", forbidden)
    report = gate.diagnose_future_sunday_bundle(
        tmp_path, race_date=TARGET,
        observed_at=datetime.fromisoformat("2026-11-01T08:00:00+09:00"),
        model_mode="dual",
    )
    assert report["blockers"] == ["PRE_RACE_WINDOW_EXPIRED"]
    assert report["publicationAuthorized"] is False
