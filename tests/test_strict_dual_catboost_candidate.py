"""Dual real-model candidate tests use fictional local-only history."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256
import json

import pandas as pd
import pytest

from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)
from horse_racing_predictions.strict_dual_catboost_candidate import (
    fit_strict_dual_catboost_candidate,
    save_dual_candidate_for_research,
)


def _history():
    rows = []
    for race in range(18):
        race_day = (date(2022, 6, 1) + timedelta(days=race)).isoformat()
        for horse in range(1, 7):
            rows.append({
                "race_id": f"FAKE-{race:02d}",
                "race_date": race_day,
                "horse_name": f"架空馬{horse}",
                "finish_position": (horse + race) % 6 + 1,
                "post_position": horse,
                "distance_m": 1200 + (race % 3) * 200,
                "age": 3 + horse % 4,
                "carried_weight": 52 + horse % 3,
                "surface": "turf" if race % 2 else "dirt",
                "racecourse": "Fictional-A" if race % 2 else "Fictional-B",
                "win_odds": float(horse + 1),
                "popularity": 7 - horse,
            })
    return pd.DataFrame(rows)


def _sample(data=None):
    return prepare_strict_odds_free_training_sample(
        _history() if data is None else data,
        train_start="2022-06-01", train_end="2022-06-18",
    )


def _run(sample=None):
    return fit_strict_dual_catboost_candidate(
        _sample() if sample is None else sample,
        fit_through="2022-06-10", validation_from="2022-06-11",
        validation_through="2022-06-18", iterations=30,
    )


def test_real_catboost_fit_and_independent_artifacts(tmp_path, monkeypatch):
    pytest.importorskip("catboost")
    from horse_racing_predictions import strict_dual_catboost_candidate as mod
    real = mod.CatBoostProbabilityModel.predict_win_probability
    seen = []

    def inspect(self, frame, race_col="race_id"):
        assert "finish_position" not in frame
        assert "is_winner" not in frame
        assert "win_odds" not in frame
        assert "popularity" not in frame
        seen.append(id(self))
        return real(self, frame, race_col=race_col)

    monkeypatch.setattr(mod.CatBoostProbabilityModel, "predict_win_probability", inspect)
    candidate = _run()
    assert len(seen) == 2 and len(set(seen)) == 2
    assert candidate.winner.model is not candidate.outsider.model
    report = candidate.metrics
    assert report.trainingRaces == 10
    assert report.validationRaces == 8
    assert 0 <= report.winTop1Accuracy <= 1
    assert 0 <= report.outsiderCandidateHitTop3Rate <= 1
    assert report.publicationAuthorized is False
    assert report.positiveExpectedValueDemonstrated is False
    assert report.outsiderFrozenAndIndependentlyVerified is False
    output_dir = tmp_path / "candidate"
    saved = save_dual_candidate_for_research(
        candidate, destination=output_dir, source_ref="synthetic-local-fake"
    )
    assert saved["publicationAuthorized"] is False
    manifest = json.loads(
        (output_dir / "candidate_manifest.json").read_text(encoding="utf8")
    )
    assert manifest["sourceRightsIndependentlyVerified"] is False
    assert manifest["independentOutsiderModelVerified"] is False
    for fname in ("win.cbm", "outsider.cbm"):
        assert saved["artifactSha256"][fname] == sha256(
            (output_dir / fname).read_bytes()
        ).hexdigest()
    with pytest.raises(ValueError, match="fresh dir"):
        save_dual_candidate_for_research(
            candidate, destination=output_dir, source_ref="synthetic-local-fake"
        )


def test_protected_holdout_cutoff_blocks_without_loading_catboost():
    sample = _sample()
    for contaminated in (
        replace(sample, cutoff="2025-01-01"),
        replace(sample, cutoff="2026-01-01"),
    ):
        with pytest.raises(ValueError, match="protected final holdout"):
            _run(contaminated)
    with pytest.raises(ValueError, match="before final holdout"):
        fit_strict_dual_catboost_candidate(
            sample, fit_through="2022-06-10",
            validation_from="2025-01-01", validation_through="2025-06-01",
        )


def test_odds_and_unknown_leakage_are_rejected_before_catboost_training():
    sample = _sample()
    for leak in ("win_odds", "popularity", "finish_position", "future_result"):
        bad = replace(sample, features=sample.features + (leak,))
        with pytest.raises(ValueError, match="leakage|unrecognized"):
            _run(bad)
    raw = _history()
    prohibited = raw.iloc[[0]].copy()
    prohibited["race_id"] = "PROTECTED"
    prohibited["race_date"] = "2025-01-01"
    with pytest.raises(ValueError, match="protected"):
        _sample(pd.concat([raw, prohibited], ignore_index=True))


def test_prevent_unbounded_hyperparameter_or_fold_time_override():
    sample = _sample()
    with pytest.raises(ValueError, match="between 30 and 600"):
        fit_strict_dual_catboost_candidate(
            sample, fit_through="2022-06-10",
            validation_from="2022-06-11",
            validation_through="2022-06-18", iterations=0,
        )
    with pytest.raises(ValueError, match="strictly chronological"):
        fit_strict_dual_catboost_candidate(
            sample, fit_through="2022-06-15",
            validation_from="2022-06-11", validation_through="2022-06-18",
        )


def _cli():
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "train_strict_dual_pre2025_local.py"
    spec = spec_from_file_location("strict_dual_cli", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cli_args(source, dest):
    return [
        "train_strict_dual_pre2025_local.py",
        "--approved-pre2025-csv", str(source),
        "--source-ref", "synthetic-no-real-horses",
        "--output-dir", str(dest),
        "--train-start", "2022-06-01",
        "--train-end", "2022-06-18",
        "--fit-through", "2022-06-10",
        "--validation-from", "2022-06-11",
        "--validation-through", "2022-06-18",
        "--iterations", "30",
    ]


def test_local_dual_cli_rejects_missing_csv_without_creating_artifact(
    tmp_path, monkeypatch, capsys,
):
    import sys
    cli = _cli()
    destination = tmp_path / "unwritten"
    monkeypatch.setattr(sys, "argv", _cli_args(tmp_path / "missing.csv", destination))
    assert cli.main() == 2
    assert not destination.exists()
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "BLOCKED"
    assert output["publicationAuthorized"] is False


def test_local_dual_cli_rejects_mixed_protected_rows(tmp_path, monkeypatch, capsys):
    import sys
    cli = _cli()
    data = _history()
    illegal = data.iloc[[0]].copy()
    illegal["race_id"] = "HOLDOUT"
    illegal["race_date"] = "2026-10-25"
    source = tmp_path / "mixed.csv"
    pd.concat([data, illegal], ignore_index=True).to_csv(source, index=False)
    destination = tmp_path / "must-not-write"
    monkeypatch.setattr(sys, "argv", _cli_args(source, destination))
    assert cli.main() == 2
    assert not destination.exists()
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"


def test_actual_dual_catboost_cli_saves_only_nonpublic_candidates(
    tmp_path, monkeypatch, capsys,
):
    import sys
    pytest.importorskip("catboost")
    cli = _cli()
    source = tmp_path / "fictional.csv"
    _history().to_csv(source, index=False)
    destination = tmp_path / "candidate"
    monkeypatch.setattr(sys, "argv", _cli_args(source, destination))
    assert cli.main() == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["status"] == "RESEARCH_ARTIFACT_SAVED_NOT_APPROVED"
    assert report["publicationAuthorized"] is False
    assert report["positiveExpectedValueDemonstrated"] is False
    assert report["metrics"]["validationRaces"] == 8
    assert "架空馬" not in output
    assert (destination / "win.cbm").is_file()
    assert (destination / "outsider.cbm").is_file()
    assert (destination / "candidate_manifest.json").is_file()

def test_legitimately_named_but_nonexistent_past_feature_cannot_drive_catboost(
    monkeypatch,
):
    from horse_racing_predictions import strict_dual_catboost_candidate as mod
    sample = _sample()
    frame = sample.frame.copy()
    # Former prefix-based allowlist admitted these untrusted columns.
    frame["horse_past_future_winner"] = frame["is_winner"].astype(float)
    malicious = replace(
        sample, frame=frame,
        features=sample.features + ("horse_past_future_winner",),
    )

    def must_not_fit(*_args, **_kwargs):
        raise AssertionError("model training ran before label-leakage gate")

    monkeypatch.setattr(mod.CatBoostProbabilityModel, "fit", must_not_fit)
    with pytest.raises(ValueError, match="unrecognized research feature"):
        _run(malicious)
