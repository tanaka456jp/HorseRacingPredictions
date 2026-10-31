"""Real CatBoost dual inference with fictional local race cards only."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
import json

import pandas as pd
import pytest

from horse_racing_predictions import strict_dual_catboost_candidate as training
from horse_racing_predictions.dual_candidate_private_preview import (
    load_dual_research_candidate, private_dual_sunday_preview,
)
from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)
from test_strict_dual_catboost_candidate import _history

DATE = "2026-11-01"
FRIDAY = datetime.fromisoformat("2026-10-30T19:00:00+09:00")


class _FrozenResearchFixtureClock(datetime):
    """A fabricated model really predates the fabricated Friday preview.

    Tests must not fail when the actual calendar advances beyond Oct 2026.
    This overrides the clock only inside synthetic artifact creation, not the
    production checks which reject model artifacts generated after forecast.
    """
    @classmethod
    def now(cls, tz=None):
        fixed = datetime(2026, 10, 30, 4, 0, tzinfo=timezone.utc)
        return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)


def _artifact(tmp_path):
    pytest.importorskip("catboost")
    sample = prepare_strict_odds_free_training_sample(
        _history(), train_start="2022-06-01", train_end="2022-06-18",
    )
    candidate = training.fit_strict_dual_catboost_candidate(
        sample, fit_through="2022-06-10",
        validation_from="2022-06-11", validation_through="2022-06-18",
        iterations=30,
    )
    path = tmp_path / "research-candidate"
    with patch.object(training, "datetime", _FrozenResearchFixtureClock):
        training.save_dual_candidate_for_research(
            candidate, destination=path, source_ref="synthetic-fake-no-license",
        )
    return path


def _fake_recent_and_entries():
    rows = []
    for i in range(1, 7):
        rows.append({
            "race_id": "FICTIONAL-20261024",
            "race_date": "2026-10-24",
            "horse_name": f"架空馬{i}",
            "finish_position": i,
            "post_position": i,
            "surface": "turf", "racecourse": "Fictional-A",
            "distance_m": 1600, "age": 3 + i % 4,
            "carried_weight": 53 + i % 3,
        })
    ids = tuple(
        f"JRA-20261101-{venue}-{i:02d}"
        for venue in ("TOKYO", "KYOTO") for i in range(1, 13)
    )
    entries = []
    for rid in ids:
        for i in range(1, 7):
            entries.append({
                "race_id": rid, "race_date": DATE,
                "horse_name": f"架空馬{i}", "post_position": i,
                "surface": "turf", "racecourse": "Fictional-A",
                "distance_m": 1600, "age": 3 + i % 4,
                "carried_weight": 53 + i % 3,
            })
    return pd.DataFrame(rows), pd.DataFrame(entries), ids


def test_two_signed_by_checksum_binaries_actually_predict_with_independent_outsider(tmp_path):
    directory = _artifact(tmp_path)
    loaded = load_dual_research_candidate(directory)
    assert loaded.winner.model is not loaded.outsider.model
    assert loaded.train_end == "2022-06-10"
    history, entries, ids = _fake_recent_and_entries()
    result = private_dual_sunday_preview(
        loaded, history=history, entries=entries,
        expected_race_ids=ids, race_date=DATE, observed_at=FRIDAY,
    )
    assert result["raceCount"] == 24
    assert result["runnerCount"] == 144
    assert result["bothActualModelsExecuted"] is True
    assert len(result["winModelOutputSha256"]) == 64
    assert len(result["outsiderSelectionSha256"]) == 64
    assert result["publicationAuthorized"] is False
    assert result["sourceRightsIndependentlyVerified"] is False
    assert result["positiveExpectedValueDemonstrated"] is False
    assert "架空馬" not in json.dumps(result, ensure_ascii=False)


def test_tampered_native_binary_and_manifest_false_release_blocked(tmp_path):
    directory = _artifact(tmp_path)
    path = directory / "outsider.cbm"
    path.write_bytes(path.read_bytes() + b"unapproved")
    with pytest.raises(ValueError, match="checksum"):
        load_dual_research_candidate(directory)
    assert not (directory / "ready_to_publish.txt").exists()
    path = directory / "candidate_manifest.json"
    doc = json.loads(path.read_text(encoding="utf8"))
    doc["publicationAuthorized"] = True
    path.write_text(json.dumps(doc), encoding="utf8")
    with pytest.raises(ValueError, match="may not authorize"):
        load_dual_research_candidate(directory)


def test_native_research_artifact_rejects_fake_2025_training(tmp_path):
    directory = _artifact(tmp_path)
    path = directory / "candidate_manifest.json"
    doc = json.loads(path.read_text(encoding="utf8"))
    doc["trainEnd"] = "2026-01-01"
    doc["researchMetrics"]["fitThrough"] = "2026-01-01"
    path.write_text(json.dumps(doc), encoding="utf8")
    with pytest.raises(ValueError, match="protected holdout"):
        load_dual_research_candidate(directory)


def test_must_not_allow_post_race_or_stale_model_reinterpretation(tmp_path):
    directory = _artifact(tmp_path)
    loaded = load_dual_research_candidate(directory)
    history, entries, ids = _fake_recent_and_entries()
    with pytest.raises(ValueError, match="08:00"):
        private_dual_sunday_preview(
            loaded, history=history, entries=entries,
            expected_race_ids=ids, race_date=DATE,
            observed_at=datetime.fromisoformat("2026-11-01T08:00:00+09:00"),
        )
    history["race_date"] = "2026-10-01"
    with pytest.raises(ValueError, match="stale"):
        private_dual_sunday_preview(
            loaded, history=history, entries=entries,
            expected_race_ids=ids, race_date=DATE, observed_at=FRIDAY,
        )
