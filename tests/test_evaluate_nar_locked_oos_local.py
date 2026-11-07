"""Offline NAR curated JSON safety; all identities and returns are fictional."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from datetime import timedelta
import json
import sys

import pytest
from test_nar_locked_oos_economics import race

entry=Path(__file__).resolve().parents[1]/"scripts"/"evaluate_nar_locked_oos_local.py"
spec=spec_from_file_location("local_nar_oos_economic_probe",entry)
assert spec is not None and spec.loader is not None
mod=module_from_spec(spec)
spec.loader.exec_module(mod)


def _doc():
    key,win,baseline,settled=race()
    def f(x):
        return {
            "race_id":x.race_id,"race_day":x.race_day,
            "post_time_utc":x.post_time_utc.isoformat(),
            "predicted_at_utc":x.predicted_at_utc.isoformat(),
            "model_ref":x.model_ref,
            "model_fit_through_day":x.model_fit_through_day,
            "winner_scores":dict(x.winner_scores),
            "outsider_scores":dict(x.outsider_scores),
            "odds_used_in_selection":False,
        }
    return {
        "schema":"NARLockedOOSCandidate.v1",
        "expected_races":{key:win.race_day},
        "documented_exclusions":{},
        "candidate_forecasts":[f(win)],
        "benchmark_forecasts":[f(baseline)],
        "settlements":[{
            "race_id":settled.race_id,
            "finishing_positions":dict(settled.finishing_positions),
            "win_return_per_100_yen":dict(settled.win_return_per_100_yen),
            "place_return_per_100_yen":dict(settled.place_return_per_100_yen),
        }],
        "extra_cost_yen_per_race":0,
    }


def test_curated_json_read_only_screening_does_not_claim_rights_or_ev(tmp_path):
    path=tmp_path/"fictional.json"
    path.write_text(json.dumps(_doc()),encoding="utf-8")
    value=mod.evaluate_local_curated_nar(path)
    assert value["scheduled_races"]==1
    assert value["paired_settled_races"]==1
    assert value["status"]=="NAR_OOS_INSUFFICIENT_PREREGISTERED_EVIDENCE"
    assert not value["economic_diagnostic_performed"]
    assert not value["observed_source_rights_independently_verified"]
    assert not value["positive_expected_value_demonstrated"]
    assert value["historical_roi_is_not_future_expected_value"]
    assert "架空競馬場" not in json.dumps(value,ensure_ascii=False)


def test_duplicate_key_and_odds_feature_not_accepted(tmp_path):
    path=tmp_path/"fake.json"
    path.write_text('{"schema":"NARLockedOOSCandidate.v1","schema":"tampered"}',
                    encoding="utf-8")
    with pytest.raises(ValueError,match="DUPLICATE_PRIVATE_JSON_FIELD"):
        mod.evaluate_local_curated_nar(path)
    doc=_doc()
    doc["candidate_forecasts"][0]["odds"]=2.1
    path.write_text(json.dumps(doc),encoding="utf-8")
    with pytest.raises(ValueError,match="PRIVATE_NAR_OOS_FORECAST_STRUCTURE_INVALID"):
        mod.evaluate_local_curated_nar(path)


def test_protected_2025_record_yields_generic_private_safe_block(tmp_path,monkeypatch,capsys):
    path=tmp_path/"MY_CONFIDENTIAL_RACE.json"
    doc=_doc()
    entry=doc["candidate_forecasts"][0]
    entry["race_day"]="2025-01-01"
    path.write_text(json.dumps(doc),encoding="utf-8")
    monkeypatch.setattr(sys,"argv",[
        "evaluate_nar_locked_oos_local.py","--reviewed-local-json",str(path),
        "--no-provider-access",
    ])
    assert mod.main()==2
    stdout=capsys.readouterr().out
    obj=json.loads(stdout)
    assert obj["status"]=="BLOCKED"
    assert not obj["positive_expected_value_demonstrated"]
    assert "MY_CONFIDENTIAL_RACE" not in stdout
    assert "架空競馬場" not in stdout


def test_missing_file_and_symlinked_parent_blocked(tmp_path):
    with pytest.raises(ValueError,match="SPECIFIC_CURATED_PRIVATE_JSON_REQUIRED"):
        mod.evaluate_local_curated_nar(tmp_path/"not-present.json")
    original=tmp_path/"private"
    original.mkdir()
    f=original/"local.json"
    f.write_text(json.dumps(_doc()),encoding="utf-8")
    linked=tmp_path/"linked"
    try:
        linked.symlink_to(original,target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip("symlinks not permitted by environment")
    with pytest.raises(ValueError,match="SPECIFIC_CURATED_PRIVATE_JSON_REQUIRED"):
        mod.evaluate_local_curated_nar(linked/"local.json")


def test_underpowered_cli_exit_two_no_publication(tmp_path,monkeypatch,capsys):
    path=tmp_path/"fictional.json"
    path.write_text(json.dumps(_doc()),encoding="utf-8")
    monkeypatch.setattr(sys,"argv",[
        "evaluate_nar_locked_oos_local.py","--reviewed-local-json",str(path),
        "--no-provider-access",
    ])
    assert mod.main()==2
    output=json.loads(capsys.readouterr().out)
    assert output["economic_diagnostic_performed"] is False
    assert output["authorized_for_note"] is False
    assert output["authorized_for_betting"] is False
