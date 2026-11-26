"""Fictional Actions metadata/logs: no real race or provider request."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import verify_nar_catboost_hosted_receipt as M


def fixture():
    run = dict(id=42, repository={"full_name": M._REPO},
               head_repository={"full_name": M._REPO}, path=M._WORKFLOW,
               head_branch=M._BRANCH, event="push", status="completed",
               conclusion="success", run_attempt=1, created_at="2026-11-10T00:00:00Z")
    job = dict(run_id=42, name=M._JOB, status="completed", conclusion="success",
               runner_group_name="GitHub Actions", labels=["ubuntu-latest"],
               started_at="2026-11-10T00:05:00Z", completed_at="2026-11-10T00:06:00Z")
    r = dict(schema=M._SCHEMA, status=M._STATUS, blinded_digest="a"*64,
             github_hosted_observed_utc="2026-11-10T00:05:30Z",
             earliest_off_utc="2026-11-10T02:35:00Z", race_day_jst="2026-11-10",
             frozen_races_declared=1, three_of_five_feature_ablation=True,
             actual_bets=0, private_forecast_contents_verified=False,
             source_licence_and_roster_independently_verified=False,
             prospective_hit_rate_measured=False, prospective_roi_measured=False,
             positive_ev_proven=False, private_model_or_horse_data_uploaded=False)
    frozen=SimpleNamespace(jurisdiction="NAR", race_day_jst="2026-11-10",
        generated_utc="2026-11-10T00:04:00Z", source_asof_utc="2026-11-10T00:00:00Z",
        races=[SimpleNamespace(off_utc="2026-11-10T02:35:00Z")])
    return run, job, r, frozen


def log(r):
    return "2026-11-10T00:05:31Z "+json.dumps(r)


def test_receipt_live_metadata_contract_and_private_match():
    run, job, r, frozen=fixture()
    receipt=M.validate_hosted_run_receipt(run,job,log(r),run_id=42)
    assert M.match_private_receipt(frozen,{"blinded_digest":"a"*64},receipt)
    with pytest.raises(ValueError,match="MISMATCH"):
        M.match_private_receipt(frozen,{"blinded_digest":"b"*64},receipt)


@pytest.mark.parametrize("issue",["skipped","rerun","self_hosted","duplicate","late","wrong_count"])
def test_fail_closed(issue):
    run,job,r,frozen=fixture()
    if issue=="skipped":
        job["conclusion"]="skipped"
    elif issue=="rerun":
        run["run_attempt"]=2
    elif issue=="self_hosted":
        job["labels"].append("self-hosted")
    elif issue=="late":
        r["github_hosted_observed_utc"]="2026-11-10T02:34:00Z"
    elif issue=="wrong_count":
        r["frozen_races_declared"]=2
    with pytest.raises(ValueError):
        result=M.validate_hosted_run_receipt(run,job,log(r)*1 if issue!="duplicate" else log(r)+"\n"+log(r),run_id=42)
        M.match_private_receipt(frozen,{"blinded_digest":"a"*64},result)
