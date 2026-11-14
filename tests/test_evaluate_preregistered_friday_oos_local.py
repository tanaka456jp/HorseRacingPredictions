"""Fictional local-operator JSON handoff never grants real EV or note rights."""
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from test_friday_oos_admission import _case

# This repository deliberately keeps scripts/ as standalone CLIs.
# Import by file path, as other CLI tests do, without changing sys.path.
_script_path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_preregistered_friday_oos_local.py"
_spec = spec_from_file_location("evaluate_preregistered_friday_oos_local", _script_path)
assert _spec is not None and _spec.loader is not None
_cli = module_from_spec(_spec)
_spec.loader.exec_module(_cli)
research_aggregate = _cli.research_aggregate
main = _cli.main


def _document():
    rid, f, p = _case()
    return {
        "schema": "JRAFridayLockedOOSCandidate.v1",
        "expected_races": {rid: f.race_day},
        "documented_exclusions": {},
        "forecasts": [{
            "race_id": f.race_id,
            "race_day": f.race_day,
            "post_time_utc": f.post_time_utc.isoformat(),
            "predicted_at_utc": f.predicted_at_utc.isoformat(),
            "model_ref": f.model_ref,
            "model_fit_through_day": f.model_fit_through_day,
            "winner_scores": dict(f.winner_scores),
            "outsider_scores": dict(f.outsider_scores),
            "odds_used_in_selection": False,
        }],
        "settlements": [{
            "race_id": p.race_id,
            "finishing_positions": dict(p.finishing_positions),
            "win_return_per_100_yen": dict(p.win_return_per_100_yen),
            "place_return_per_100_yen": dict(p.place_return_per_100_yen),
        }],
    }


def test_local_pre_registered_one_race_only_reports_screening_not_roi(tmp_path):
    file = tmp_path / "candidate.json"
    file.write_text(json.dumps(_document()), encoding="utf-8")
    result = research_aggregate(file)
    assert result["scheduledRaces"] == 1
    assert result["admittedForecasts"] == 1
    assert result["minimumSampleSizePassed"] is False
    assert result["economicEvaluationPerformed"] is False
    assert "diagnosticHistoricalROI" not in result
    assert result["notePublicationAuthorized"] is False
    assert result["positiveExpectedValueDemonstrated"] is False


def test_duplicate_json_key_and_market_fields_rejected(tmp_path):
    file = tmp_path / "candidate.json"
    file.write_text('{"schema":"JRAFridayLockedOOSCandidate.v1",'
                    '"schema":"bad"}', encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="CANDIDATE_DUPLICATE_JSON_KEY"):
        research_aggregate(file)
    modified = _document()
    modified["forecasts"][0]["win_odds"] = [1.2]
    file.write_text(json.dumps(modified), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_FORECAST_ENVELOPE_INVALID"):
        research_aggregate(file)


def test_cli_safe_refusal_omits_private_filename_and_horse_data(
        tmp_path, monkeypatch, capsys):
    file = tmp_path / "MY_SECRET_PRIVATE_HORSE_NAME.json"
    data = _document()
    data["forecasts"][0]["race_day"] = "2026-11-02"
    file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "evaluate_preregistered_friday_oos_local",
        "--candidate-json", str(file), "--local-review-only",
    ])
    assert main() == 2
    output = capsys.readouterr().out
    assert "BLOCKED" in output
    assert "MY_SECRET_PRIVATE" not in output
    assert "FICTIONAL_" not in output
    assert '"positiveExpectedValueDemonstrated": false' in output


def test_cli_returns_nonzero_for_missing_sample_size(tmp_path, monkeypatch, capsys):
    file = tmp_path / "candidate.json"
    file.write_text(json.dumps(_document()), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "evaluate_preregistered_friday_oos_local",
        "--candidate-json", str(file), "--local-review-only",
    ])
    assert main() == 2
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "BLOCKED_INSUFFICIENT_PREREGISTERED_OOS_SAMPLE"
    assert record["positiveExpectedValueDemonstrated"] is False
    assert record["notePublicationAuthorized"] is False
