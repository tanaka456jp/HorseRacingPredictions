"""Record a public digest-only GitHub Actions receipt, without NAR data.

workflow_dispatch ONLY on default main after review/merge; never accept
local timestamps as independent GitHub creation-time verification.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from horse_racing_predictions.nar_forward_hosted_witness import (
    validate_nar_github_hosted_receipt,
)

_MAX_EVENT_BYTES = 64_000


def create_hosted_receipt_from_event(
    event: dict, environ: dict[str, str], host_clock: datetime,
) -> dict:
    if (type(event) is not dict or
            environ.get("GITHUB_ACTIONS") != "true" or
            environ.get("GITHUB_SERVER_URL") != "https://github.com" or
            environ.get("EXPECTED_RUNNER_ENVIRONMENT") != "github-hosted"):
        raise ValueError("NAR_GH_RECEIPT_NOT_GITHUB_HOSTED")
    proof = validate_nar_github_hosted_receipt(
        inputs=event.get("inputs"),
        repository=environ.get("GITHUB_REPOSITORY", ""),
        ref=environ.get("GITHUB_REF", ""),
        event_name=environ.get("GITHUB_EVENT_NAME", ""),
        run_id=environ.get("GITHUB_RUN_ID", ""),
        run_attempt=environ.get("GITHUB_RUN_ATTEMPT", ""),
        observed_utc=host_clock,
    )
    # Explicit allowlist: never echo arbitrary event JSON or input fields.
    return {
        "schema": proof.schema,
        "status": proof.status,
        "digestSha256": proof.commitment_digest,
        "githubRunId": proof.github_run_id,
        "githubRunAttempt": proof.github_run_attempt,
        "githubRunUrl": proof.run_url,
        "githubRepository": proof.github_repository,
        "githubRef": proof.github_ref,
        "hostLoggedAtUtc": proof.host_logged_at_utc,
        "earliestScheduledOffUtc": proof.scheduled_earliest_off_utc,
        "raceDayJst": proof.race_day_jst,
        "registeredFlatRaces": proof.declared_flat_races,
        "fictionalDemo": proof.fictional_demo,
        "githubRunCreatedAtIndependentlyVerified": False,
        "githubDispatchInputsIndependentlyVerified": False,
        "privateForecastSnapshotIndependentlyVerified": False,
        "officialPostTimeVerified": False,
        "realizedRoiAuthorized": False,
        "positiveExpectedValueDemonstrated": False,
        "privateRaceHorseDataTransferred": False,
        "protectedOosOpened": False,
    }


def main() -> int:
    try:
        path = Path(os.environ["GITHUB_EVENT_PATH"])
        if (not path.is_file() or path.is_symlink()
                or not 0 < path.stat().st_size <= _MAX_EVENT_BYTES):
            raise ValueError("NAR_GH_RECEIPT_UNSAFE_EVENT_PATH")
        event = json.loads(path.read_text(encoding="utf-8"))
        result = create_hosted_receipt_from_event(
            event, dict(os.environ), datetime.now(timezone.utc),
        )
        print(json.dumps(result, sort_keys=True, ensure_ascii=True,
                         allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            OverflowError):
        # No exception, private path, arbitrary input or source-data echo.
        print(json.dumps({
            "schema": "NAR.GitHubHostedDigestReceipt.v1",
            "status": "NAR_GH_HOSTED_DIGEST_RECEIPT_HOLD",
            "positiveExpectedValueDemonstrated": False,
            "privateRaceHorseDataTransferred": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
