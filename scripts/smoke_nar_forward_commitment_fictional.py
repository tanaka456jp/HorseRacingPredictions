"""Synthetic-only, offline NAR future forecast digest smoke for PC2.

No source archives, provider calls, network, money, credentials or file writes.
Only fixed aggregate booleans may be printed to the Windows runner log.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

from horse_racing_predictions.nar_forward_preoff_commitment import (
    NarProspectiveForecast, seal_nar_prospective_batch,
    verify_nar_prospective_batch,
)

_JST = timezone(timedelta(hours=9))
_SALT = bytes(range(32))  # Synthetic fixture only; never use in production.


def run_fictional_smoke() -> dict:
    off = datetime(2026, 11, 14, 15, tzinfo=_JST)
    seen = off - timedelta(days=1, hours=4)
    issued = off - timedelta(days=1, hours=2)
    cases = []
    for number in (1, 2):
        cases.append(NarProspectiveForecast(
            race_id=f"NAR:20261114:架空競馬場:{number:02d}",
            race_day="2026-11-14",
            scheduled_off_utc=off,
            generated_at_utc=issued,
            roster_observed_at_utc=seen,
            model_source_sha256="a" * 64,
            model_fit_through_day="2026-11-12",
            winner_scores={str(i): float(10 - i) for i in range(1, 9)},
            outsider_scores={
                str(i): float(20 if i == 6 else 1) for i in range(1, 9)
            },
        ))
    calendar = {x.race_id: x.race_day for x in cases}
    proof = seal_nar_prospective_batch(
        calendar, cases, private_salt=_SALT,
    )
    baseline = verify_nar_prospective_batch(
        proof, calendar, list(reversed(cases)), private_salt=_SALT,
    )
    changed = replace(cases[0], winner_scores={
        **cases[0].winner_scores, "1": 999.0,
    })
    tamper = verify_nar_prospective_batch(
        proof, calendar, [changed, cases[1]], private_salt=_SALT,
    )
    assert baseline.sha256_matches_private_snapshot
    assert not tamper.sha256_matches_private_snapshot
    assert proof.registered_flat_races == proof.locked_forecasts == 2
    assert not baseline.independently_timestamped_before_off
    assert not proof.prior_to_result_publication_proven
    assert not baseline.authorized_for_realized_roi
    assert not baseline.positive_expected_value_demonstrated
    return {
        "schema": "NAR.PC2.FictionalFutureCommitmentSmoke.v1",
        "result": "PASS",
        "fictionalRaceCount": 2,
        "privateSnapshotIntegrityVerified": True,
        "postFreezeScoreTamperingDetected": True,
        "thirdPartyTimestampVerified": False,
        "realNARRecordsOpened": 0,
        "sourcePrivateFilesRead": False,
        "protectedHoldoutOpened": False,
        "providerCalls": 0,
        "realWagers": 0,
        "actualEvDemonstrated": False,
        "dataUploaded": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(run_fictional_smoke(), sort_keys=True))
    except Exception:
        # No tracebacks, source text, private paths or horse IDs.
        print(json.dumps({
            "schema": "NAR.PC2.FictionalFutureCommitmentSmoke.v1",
            "result": "HOLD",
            "realNARRecordsOpened": 0,
            "actualEvDemonstrated": False,
            "dataUploaded": False,
        }, sort_keys=True))
        raise SystemExit(2) from None
