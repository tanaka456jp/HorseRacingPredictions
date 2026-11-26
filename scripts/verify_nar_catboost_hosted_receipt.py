"""Verify a real GitHub-hosted NAR blinded receipt, then match private freeze.

No racing provider access, source upload, betting, or source-rights claim.
The hosted fetch uses the repository's read-only Actions token via gh.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import re
import subprocess

_REPO = "tanaka456jp/HorseRacingPredictions"
_BRANCH = "feature/weekly-odds-free-note-20261021"
_WORKFLOW = ".github/workflows/nar-pc2-future-catboost-preoff-freeze-receipt.yml"
_JOB = "github-hosted-preoff-blinded-receipt"
_SCHEMA = "NAR.GitHubHostedCatBoostPartialPreoffReceipt.v1"
_STATUS = "BLINDED_3_OF_5_MODEL_COMMITMENT_RECEIVED_BEFORE_FIRST_OFF"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _time(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.utcoffset() is None:
        raise ValueError("RECEIPT_TIME_NAIVE")
    return t.astimezone(timezone.utc)


def _validate_receipt(r):
    if (type(r) is not dict or r.get("schema") != _SCHEMA
            or r.get("status") != _STATUS
            or type(r.get("blinded_digest")) is not str
            or not _SHA.fullmatch(r["blinded_digest"])
            or type(r.get("frozen_races_declared")) is not int
            or not 1 <= r["frozen_races_declared"] <= 500
            or r.get("three_of_five_feature_ablation") is not True
            or type(r.get("actual_bets")) is not int or r["actual_bets"] != 0
            or any(r.get(k) is not False for k in (
                "private_forecast_contents_verified",
                "source_licence_and_roster_independently_verified",
                "prospective_hit_rate_measured", "prospective_roi_measured",
                "positive_ev_proven", "private_model_or_horse_data_uploaded"))):
        raise ValueError("RECEIPT_CONTRACT_INVALID")
    off, received = _time(r["earliest_off_utc"]), _time(r["github_hosted_observed_utc"])
    if (received >= off - timedelta(minutes=5)
            or off.astimezone(timezone(timedelta(hours=9))).date().isoformat()
            != r.get("race_day_jst")):
        raise ValueError("RECEIPT_TOO_LATE_OR_WRONG_DAY")
    return received, off


def validate_hosted_run_receipt(run, job, log, *, run_id):
    """Check live API metadata and one exact timestamped receipt log record."""
    if (type(run_id) is not int or run_id < 1 or run.get("id") != run_id
            or run.get("repository", {}).get("full_name") != _REPO
            or run.get("head_repository", {}).get("full_name") != _REPO
            or run.get("path") != _WORKFLOW or run.get("head_branch") != _BRANCH
            or run.get("event") not in ("push", "workflow_dispatch")
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or run.get("run_attempt") != 1
            or job.get("run_id") != run_id or job.get("name") != _JOB
            or job.get("status") != "completed" or job.get("conclusion") != "success"
            or job.get("runner_group_name") != "GitHub Actions"
            or "ubuntu-latest" not in job.get("labels", [])
            or "self-hosted" in job.get("labels", [])):
        raise ValueError("RECEIPT_HOSTED_RUN_NOT_VERIFIED")
    if len(log) > 2_000_000:
        raise ValueError("RECEIPT_LOG_TOO_LARGE")
    records = []
    for line in log.splitlines():
        # Raw Actions job log lines are prefixed by UTC log timestamps.
        match = re.fullmatch(r"(\S+)\s+(\{.*\})", line.strip())
        if not match:
            continue
        try:
            obj = json.loads(match[2])
        except ValueError:
            continue
        if type(obj) is dict and obj.get("schema") == _SCHEMA:
            records.append((_time(match[1]), obj))
    if len(records) != 1:
        raise ValueError("RECEIPT_LOG_MISSING_OR_AMBIGUOUS")
    logged, r = records[0]
    received, off = _validate_receipt(r)
    if not (_time(run["created_at"]) <= _time(job["started_at"])
            <= received <= logged <= _time(job["completed_at"])
            and logged < off - timedelta(minutes=5)
            and logged - received <= timedelta(minutes=1)):
        raise ValueError("RECEIPT_LOG_CHRONOLOGY_INVALID")
    return r


def match_private_receipt(frozen, doc, receipt):
    """Match an already API-verified receipt to the locally checked forecast."""
    received, off = _validate_receipt(receipt)
    earliest = min(_time(r.off_utc) for r in frozen.races)
    if (frozen.jurisdiction != "NAR"
            or receipt["blinded_digest"] != doc.get("blinded_digest")
            or receipt["race_day_jst"] != frozen.race_day_jst
            or receipt["frozen_races_declared"] != len(frozen.races)
            or off != earliest or _time(frozen.generated_utc) > received
            or _time(frozen.source_asof_utc) > _time(frozen.generated_utc)):
        raise ValueError("RECEIPT_PRIVATE_FORECAST_MISMATCH")
    return True


def _api(endpoint):
    return subprocess.check_output(["gh", "api", endpoint], text=True,
                                   encoding="utf-8", timeout=30)


def main():
    try:
        raw = os.environ["RECEIPT_RUN_ID"]
        if not re.fullmatch(r"[1-9][0-9]{0,19}", raw):
            raise ValueError("RECEIPT_RUN_ID_INVALID")
        run_id = int(raw)
        base = f"repos/{_REPO}/actions"
        run = json.loads(_api(f"{base}/runs/{run_id}"))
        jobs = json.loads(_api(f"{base}/runs/{run_id}/jobs?per_page=100"))
        if jobs["total_count"] != len(jobs["jobs"]):
            raise ValueError("RECEIPT_JOB_LIST_INCOMPLETE")
        matches = [j for j in jobs["jobs"] if j.get("name") == _JOB]
        if len(matches) != 1:
            raise ValueError("RECEIPT_JOB_AMBIGUOUS")
        job = matches[0]
        if type(job.get("id")) is not int or job["id"] < 1:
            raise ValueError("RECEIPT_JOB_ID_INVALID")
        r = validate_hosted_run_receipt(run, job,
                    _api(f"{base}/jobs/{job['id']}/logs"), run_id=run_id)
        print(json.dumps(r, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        print("NAR_GITHUB_HOSTED_RECEIPT_HOLD")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
