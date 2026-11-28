"""Fictional-only offline integration test; no private real racing sources."""
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import freeze_nar_paired_three_series_private as M
from test_freeze_nar_partial_catboost_daily_private import fake_model, DAY, OBS, GEN
from test_nar_official_daily_preoff import fictional_daily_zip
from horse_racing_predictions.nar_paired_future_comparison import verify_paired_commitment


def stage(root, monkeypatch, *, wrong_name=False):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    monkeypatch.setattr(M, "load_nar_private_dual_candidate", lambda _: fake_model())
    capture = root / "nar-prospective-captures"
    staged = root / "forward-model-inputs"
    capture.mkdir()
    staged.mkdir()
    blob = fictional_daily_zip()
    source = capture / "20261110_20261110T000000Z_race.zip"
    source.write_bytes(blob)
    salt = b"x"*32
    source.with_name(source.name.replace("_race.zip", "_private_provenance.json")).write_text(
        json.dumps({"schema": "NAR.OfficialDailyPreoffCapture.v1",
                    "salt_hex_PRIVATE": salt.hex(),
                    "salted_zip_sha256_PRIVATE": sha256(
                        b"NAR_OFFICIAL_DAILY_RACE_V1" + bytes([0]) + salt + blob).hexdigest(),
                    "host_captured_utc": OBS.isoformat()}), encoding="utf-8")
    entries, history = [], []
    for race in (1, 2):
        for horse in range(1, 5):
            name = f"架空馬{race}-{horse}"
            entries.append(dict(race_id=f"NAR:20261110:架空地方場:{race:02d}",
                horse_id=str(horse), horse_name=name if not wrong_name else name+"別",
                birth_ymd="20210304", reviewed_starts=8 if horse==1 else 0,
                reviewed_wins=2 if horse==1 else 0, reviewed_top3=4 if horse==1 else 0))
            if horse == 1:
                for offset, rank in enumerate((1, 1, 2, 3, 4, 5, 6, 7), 1):
                    date = DAY - timedelta(days=offset)
                    history.append(dict(horse_name=name, birth_ymd="20210304",
                        race_day_jst=date.isoformat(),
                        result_released_utc=date.isoformat()+"T10:00:00Z",
                        official_status="FINISHED", finish_rank=rank))
    e = staged / "20261110_NAR_reviewed_entries.csv"
    h = staged / "20261110_NAR_reviewed_prior_history.csv"
    pd.DataFrame(entries).to_csv(e, index=False, encoding="utf-8")
    pd.DataFrame(history).to_csv(h, index=False, encoding="utf-8")
    (staged / "20261110_NAR_paired_review.json").write_text(json.dumps({
        "schema": "NAR.PC2.PairedInputReview.v1", "race_day_jst": DAY.isoformat(),
        "source_sha256_PRIVATE": {"official_preoff_zip": sha256(blob).hexdigest(),
            "reviewed_entries": sha256(e.read_bytes()).hexdigest(),
            "reviewed_prior_history": sha256(h.read_bytes()).hexdigest()},
        "permitted_prior_history_reviewed": True, "same_scope_career_counts_reviewed": True,
        "horse_birth_identity_reviewed": True, "protected_holdout_used": False,
    }), encoding="utf-8")
    return capture / "20261110_NAR_paired_three_series_PRIVATE.json"


def test_complete_paired_freeze_is_private_exclusive_and_verifiable(tmp_path, monkeypatch):
    target = stage(tmp_path, monkeypatch)
    out = M.freeze(tmp_path, clock=lambda: GEN)
    record = json.loads(target.read_text(encoding="utf-8"))
    assert out["races"] == 2 and out["runners"] == 8
    assert verify_paired_commitment(record, out["blinded_digest"])
    assert not out["independent_preoff_receipt_verified"]
    assert "salt_hex_PRIVATE" not in out and "payload_PRIVATE" not in out
    initial = target.read_bytes()
    with pytest.raises(ValueError, match="ALREADY_FROZEN"):
        M.freeze(tmp_path, clock=lambda: GEN)
    assert target.read_bytes() == initial


def test_reviewed_name_mismatch_blocks_freeze(tmp_path, monkeypatch):
    target = stage(tmp_path, monkeypatch, wrong_name=True)
    with pytest.raises(ValueError, match="HORSE_IDENTITY_MISMATCH"):
        M.freeze(tmp_path, clock=lambda: GEN)
    assert not target.exists()


def test_changed_input_bytes_fail_review_hash(tmp_path, monkeypatch):
    target = stage(tmp_path, monkeypatch)
    path = tmp_path / "forward-model-inputs" / "20261110_NAR_reviewed_prior_history.csv"
    path.write_bytes(path.read_bytes()+b"\n")
    with pytest.raises(ValueError, match="EXPLICIT_REVIEW_REQUIRED"):
        M.freeze(tmp_path, clock=lambda: GEN)
    assert not target.exists()


def test_inference_finishing_too_late_never_writes(tmp_path, monkeypatch):
    target = stage(tmp_path, monkeypatch)
    stamps = iter([GEN, GEN, OBS+timedelta(hours=2, minutes=30)])
    with pytest.raises(ValueError, match="TOO_LATE"):
        M.freeze(tmp_path, clock=lambda: next(stamps))
    assert not target.exists()
