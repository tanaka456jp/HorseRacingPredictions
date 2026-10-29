"""Private source-pair feasibility: all fixtures fictional and offline."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json

import pytest

from horse_racing_predictions.paired_source_readiness import (
    inspect_paired_sources,
)
from horse_racing_predictions.pre2025_training_csv_audit import UnsafeTrainingSource

TODAY = date(2026, 10, 29)


def _make_pair(tmp_path, *, field=5, mismatch=False,
               bad_place=False, bad_win=False, omit_payout=False):
    base = tmp_path / "fake"
    base.mkdir()
    history = base / "history.csv"
    payout = base / "payout.csv"
    hlines = ["race_id,race_date,horse_name,finish_position\n"]
    plines = [
        "race_id,race_date,horse_name,"
        "win_return_per_100_yen,place_return_per_100_yen\n"
    ]
    for i in range(1, field + 1):
        hlines.append(f"MOCK,2020-02-01,FICTIONAL_{i:02d},{i}\n")
        if i == field and omit_payout:
            continue
        h = f"FICTIONAL_{i:02d}" if not (mismatch and i == 2) else "NOT_THE_SAME"
        win = 50 if bad_win and i == 1 else (280 if i == 1 else 0)
        cutoff = 2 if field <= 7 else 3
        place = 0 if bad_place and i == 2 else (130 if i <= cutoff else 0)
        plines.append(f"MOCK,2020-02-01,{h},{win},{place}\n")
    history.write_text("".join(hlines), encoding="utf-8")
    payout.write_text("".join(plines), encoding="utf-8")
    manifests = []
    for kind, source in (("history", history), ("settlement", payout)):
        payload = {
            "schema_version": 1,
            "kind": kind,
            "provider_id": "fictional-input-rightsholder",
            "source_category": "rightsholder_licensed",
            "rights_holder": "Fictional Fixture Owner",
            "acquisition_method": "fabricated offline fixtures",
            "rights_evidence_ref": "private-synthetic-test-ref",
            "rights_scope": "private_noncommercial_research",
            "local_ml_permitted": True,
            "retention_permitted": True,
            "contract_valid_through": "2027-12-31",
            "source_sha256": sha256(source.read_bytes()).hexdigest(),
        }
        path = base / f"{kind}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        manifests.append(path)
    return history, manifests[0], payout, manifests[1]


@pytest.mark.parametrize("field", [5, 7, 8, 18])
def test_full_standard_race_match_not_licence_or_roi(tmp_path, field):
    a = _make_pair(tmp_path, field=field)
    result = inspect_paired_sources(*a, today=TODAY)
    assert result.history_rows == field
    assert result.payout_rows == field
    assert result.matched_races == 1
    assert result.matched_runners == field
    assert result.full_roster_and_payout_coverage
    assert result.eligible_first_year == result.eligible_last_year == 2020
    assert not result.verified_friday_availability
    assert not result.verified_official_payout_rights
    assert not result.authorized_for_model_training
    assert not result.authorized_for_real_roi
    assert not result.publication_authorized
    assert "FICTIONAL" not in repr(result)
    assert str(a[0]) not in repr(result)


def test_partial_payout_roster_is_refused(tmp_path):
    a = _make_pair(tmp_path, omit_payout=True)
    with pytest.raises(UnsafeTrainingSource, match="PAIR_MISSING_RESULT_OR_PAYOUT_ROW"):
        inspect_paired_sources(*a, today=TODAY)


def test_wrong_horse_cannot_be_merged_by_position(tmp_path):
    a = _make_pair(tmp_path, mismatch=True)
    with pytest.raises(UnsafeTrainingSource, match="PAIR_IDENTITY_DATE_OR_COVERAGE_MISMATCH"):
        inspect_paired_sources(*a, today=TODAY)


def test_missing_place_return_is_not_an_assumed_loss(tmp_path):
    a = _make_pair(tmp_path, bad_place=True)
    with pytest.raises(UnsafeTrainingSource, match="PAIR_PLACE_PAYOUT_CONTRADICTION"):
        inspect_paired_sources(*a, today=TODAY)


def test_win_payout_below_stake_is_refused(tmp_path):
    a = _make_pair(tmp_path, bad_win=True)
    with pytest.raises(UnsafeTrainingSource, match="PAIR_WIN_PAYOUT_CONTRADICTION"):
        inspect_paired_sources(*a, today=TODAY)


def test_four_runner_race_ineligible_for_fixed_place_strategy(tmp_path):
    a = _make_pair(tmp_path, field=4)
    with pytest.raises(UnsafeTrainingSource, match="PAIR_COMPLETE_STANDARD_RACE_REQUIRED"):
        inspect_paired_sources(*a, today=TODAY)


def test_source_expiry_is_still_enforced(tmp_path):
    a = _make_pair(tmp_path)
    payload = json.loads(a[1].read_text())
    payload["contract_valid_through"] = "2026-10-01"
    a[1].write_text(json.dumps(payload))
    with pytest.raises(UnsafeTrainingSource, match="SOURCE_RIGHTS_EXPIRED"):
        inspect_paired_sources(*a, today=TODAY)
