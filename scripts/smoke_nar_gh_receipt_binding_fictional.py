"""Offline Windows smoke for purely fictional hosted receipt/private digest join.

No source ZIP, source timestamps, real forecast, account, provider call,
protected 2025-26 holdout, purchase or ROI computation.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

from horse_racing_predictions.nar_forward_preoff_commitment import (
    NarProspectiveForecast, seal_nar_prospective_batch,
)
from horse_racing_predictions.nar_forward_hosted_witness import (
    reconcile_nar_hosted_receipt_with_private_forecasts,
    validate_nar_github_hosted_receipt,
)

JST = timezone(timedelta(hours=9))


def synthetic_windows_receipt_check() -> dict:
    off = datetime(2026, 11, 14, 15, tzinfo=JST)
    now = off - timedelta(days=1)
    fixture_rows = []
    for i in (1, 2):
        fixture_rows.append(NarProspectiveForecast(
            race_id=f"NAR:20261114:架空テスト会場:{i:02d}",
            race_day="2026-11-14",
            scheduled_off_utc=off,
            generated_at_utc=now - timedelta(hours=1),
            roster_observed_at_utc=now - timedelta(hours=2),
            model_source_sha256="b" * 64,
            model_fit_through_day="2026-11-12",
            winner_scores={str(h): float(20 - h) for h in range(1, 9)},
            outsider_scores={
                str(h): float(10 if h == 6 else 1) for h in range(1, 9)
            },
        ))
    roster = {x.race_id: x.race_day for x in fixture_rows}
    private_salt = bytes(range(32))  # FIXTURE ONLY, no production key.
    sealed = seal_nar_prospective_batch(
        roster, fixture_rows, private_salt=private_salt,
    )
    receipt = validate_nar_github_hosted_receipt(
        inputs={
            "commitment_digest": sealed.sha256_digest,
            "earliest_off_utc": "2026-11-14T06:00:00Z",
            "race_day_jst": "2026-11-14",
            "registered_flat_races": "2",
            "fictional_demo": "true",
        },
        repository="tanaka456jp/HorseRacingPredictions",
        ref="refs/heads/main", event_name="workflow_dispatch",
        run_id="42424242424", run_attempt="1", observed_utc=now,
    )
    bound = reconcile_nar_hosted_receipt_with_private_forecasts(
        receipt=receipt, commitment=sealed, expected_races=roster,
        forecasts=fixture_rows, private_salt=private_salt,
    )
    assert bound.bound_flat_races == 2
    assert bound.salted_snapshot_hash_matches
    assert bound.first_off_matches_full_private_calendar
    assert not bound.independent_proof_of_early_publication
    assert not bound.positive_expected_value_demonstrated

    changed = replace(fixture_rows[0], winner_scores={
        **fixture_rows[0].winner_scores, "1": 999.0,
    })
    tamper_rejected = False
    try:
        reconcile_nar_hosted_receipt_with_private_forecasts(
            receipt=receipt, commitment=sealed, expected_races=roster,
            forecasts=[changed, fixture_rows[1]], private_salt=private_salt,
        )
    except ValueError as exc:
        tamper_rejected = (str(exc) ==
            "NAR_GH_PRIVATE_BINDING_DIGEST_OR_COVERAGE_MISMATCH")
    assert tamper_rejected

    false_off_rejected = False
    try:
        reconcile_nar_hosted_receipt_with_private_forecasts(
            receipt=replace(receipt,
                scheduled_earliest_off_utc="2026-11-14T07:00:00Z"),
            commitment=sealed, expected_races=roster,
            forecasts=fixture_rows, private_salt=private_salt,
        )
    except ValueError as exc:
        false_off_rejected = (
            str(exc) == "NAR_GH_PRIVATE_BINDING_OFF_TIME_NOT_EARLIEST"
        )
    assert false_off_rejected

    return {
        "schema": "NAR.PC2.FictionalHostedReceiptPrivateBinding.v1",
        "status": "PASS",
        "fixtureRaces": 2,
        "privateSaltedHashMatched": True,
        "afterFreezeScoreTamperRejected": True,
        "falsifiedEarliestOffRejected": True,
        "independentGitHubAPITimestampProven": False,
        "realLicensedHorseDataRead": False,
        "actualWagersRecorded": 0,
        "protectedHoldoutOpened": False,
        "positiveExpectedValueDemonstrated": False,
        "sourceDataTransferred": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(synthetic_windows_receipt_check(), sort_keys=True))
    except Exception:
        print(json.dumps({
            "schema": "NAR.PC2.FictionalHostedReceiptPrivateBinding.v1",
            "status": "HOLD", "sourceDataTransferred": False,
            "positiveExpectedValueDemonstrated": False,
        }, sort_keys=True))
        raise SystemExit(2) from None
