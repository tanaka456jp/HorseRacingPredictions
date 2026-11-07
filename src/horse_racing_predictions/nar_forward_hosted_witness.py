"""No-data GitHub-hosted receipt input contract for prospective NAR digests.

This receives ONLY a salted hash, one earliest-off UTC timestamp, a JST
race date and a race count. Real horses, scores, roster or private salt
must NEVER enter a workflow_dispatch input, public log or CI artifact.

A GitHub-hosted job can record a digest before scheduled off; a *trusted*
attestation requires a later independent check of the GitHub run's own
created_at timestamp, its immutable dispatch input and private original
snapshot. The runner wall clock/submitter's off time are not proof alone.
Never infer data rights, real purchases or positive expected value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import re
from typing import Mapping

_REPO = "tanaka456jp/HorseRacingPredictions"
_REF = "refs/heads/main"
_JST = timezone(timedelta(hours=9))
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_RUN = re.compile(r"[1-9][0-9]{0,17}\Z")
_COUNT = re.compile(r"[1-9][0-9]{0,2}\Z")
_FIRST_DAY = date(2026, 11, 7)
_KEYS = frozenset({
    "commitment_digest", "earliest_off_utc",
    "race_day_jst", "registered_flat_races", "fictional_demo",
})


@dataclass(frozen=True)
class NarGitHubHostedReceipt:
    status: str
    schema: str
    commitment_digest: str = field(repr=False)
    github_run_id: int
    github_run_attempt: int
    github_repository: str
    github_ref: str
    run_url: str
    host_logged_at_utc: str
    scheduled_earliest_off_utc: str
    race_day_jst: str
    declared_flat_races: int
    fictional_demo: bool
    within_host_clock_lead_window: bool
    github_created_at_independently_verified: bool = False
    github_dispatch_input_independently_verified: bool = False
    private_snapshot_independently_verified: bool = False
    independently_attested_before_off: bool = False
    official_schedule_independently_verified: bool = False
    source_rights_verified: bool = False
    real_wagers_verified: bool = False
    positive_expected_value_demonstrated: bool = False
    historical_holdout_opened: bool = False


def validate_nar_github_hosted_receipt(
    *,
    inputs: Mapping[str, object],
    repository: str,
    ref: str,
    event_name: str,
    run_id: str,
    run_attempt: str,
    observed_utc: datetime,
) -> NarGitHubHostedReceipt:
    """Only structural, local validation; never grant an attestation flag.

    The actual GitHub-run creation time MUST later come from the
    GitHub-hosted REST record (not a self-provided value). The original
    salt, forecast roster, model and full score snapshot remain private.
    """
    if (not isinstance(inputs, Mapping)
            or set(inputs) != _KEYS
            or repository != _REPO or ref != _REF
            or event_name != "workflow_dispatch"
            or not isinstance(run_id, str) or not _RUN.fullmatch(run_id)
            or run_attempt != "1"):
        raise ValueError("NAR_GH_RECEIPT_UNTRUSTED_RUN_CONTEXT")
    digest = inputs["commitment_digest"]
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise ValueError("NAR_GH_RECEIPT_INVALID_DIGEST")
    off_text = inputs["earliest_off_utc"]
    if not isinstance(off_text, str) or not _UTC.fullmatch(off_text):
        raise ValueError("NAR_GH_RECEIPT_OFF_UTC_CANONICAL_REQUIRED")
    try:
        earliest = datetime.fromisoformat(off_text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("NAR_GH_RECEIPT_OFF_UTC_INVALID") from None
    day_text = inputs["race_day_jst"]
    if not isinstance(day_text, str):
        raise ValueError("NAR_GH_RECEIPT_RACE_DAY_INVALID")
    try:
        day = date.fromisoformat(day_text)
    except ValueError:
        raise ValueError("NAR_GH_RECEIPT_RACE_DAY_INVALID") from None
    if (day.isoformat() != day_text
            or day < _FIRST_DAY
            or earliest.astimezone(_JST).date() != day):
        raise ValueError("NAR_GH_RECEIPT_RACE_DAY_OR_OFF_MISMATCH")
    raw_count = inputs["registered_flat_races"]
    if (not isinstance(raw_count, str)
            or not _COUNT.fullmatch(raw_count)
            or not 1 <= int(raw_count) <= 400):
        raise ValueError("NAR_GH_RECEIPT_RACE_COUNT_INVALID")
    demo = inputs["fictional_demo"]
    if demo not in ("true", "false") or type(demo) is not str:
        raise ValueError("NAR_GH_RECEIPT_DEMO_MODE_INVALID")
    if (not isinstance(observed_utc, datetime)
            or observed_utc.tzinfo is None
            or observed_utc.utcoffset() is None):
        raise ValueError("NAR_GH_RECEIPT_HOST_UTC_REQUIRED")
    host_clock = observed_utc.astimezone(timezone.utc)
    if (host_clock >= earliest - timedelta(minutes=5)
            or host_clock < earliest - timedelta(days=7)):
        raise ValueError("NAR_GH_RECEIPT_NOT_IN_PREOFF_HOST_WINDOW")
    rid = int(run_id)
    return NarGitHubHostedReceipt(
        status=("FICTIONAL_HOSTED_RECEIPT_NO_REAL_FORECAST"
                if demo == "true" else
                "PROSPECTIVE_DIGEST_RECEIVED_EXTERNAL_PROOF_PENDING"),
        schema="NAR.GitHubHostedDigestReceipt.v1",
        commitment_digest=digest, github_run_id=rid,
        github_run_attempt=1, github_repository=_REPO,
        github_ref=_REF, run_url=(
            f"https://github.com/{_REPO}/actions/runs/{rid}"
        ),
        host_logged_at_utc=host_clock.isoformat().replace("+00:00", "Z"),
        scheduled_earliest_off_utc=off_text,
        race_day_jst=day_text,
        declared_flat_races=int(raw_count),
        fictional_demo=demo == "true",
        within_host_clock_lead_window=True,
    )
