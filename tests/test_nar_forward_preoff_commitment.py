"""Pure fictional, future-dated NAR commitment privacy/integrity checks."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from horse_racing_predictions.nar_forward_preoff_commitment import (
    NarProspectiveForecast,
    seal_nar_prospective_batch,
    verify_nar_prospective_batch,
)

JST = timezone(timedelta(hours=9))
SALT = bytes(range(32))  # TEST ONLY; actual private salt must be random.


def forecast(*, day="2026-11-14", num=1, track="架空競馬場",
             model_sha="a"*64, scores=None, outsider_scores=None,
             roster_observed_at_utc=None, generated_at_utc=None,
             scheduled_off_utc=None):
    race_id = f"NAR:{day.replace('-', '')}:{track}:{num:02d}"
    off = datetime.fromisoformat(day + "T15:00:00+09:00")
    seen = off - timedelta(hours=5)
    made = off - timedelta(hours=4)
    return NarProspectiveForecast(
        race_id=race_id, race_day=day, scheduled_off_utc=scheduled_off_utc or off,
        generated_at_utc=generated_at_utc or made,
        roster_observed_at_utc=roster_observed_at_utc or seen,
        model_source_sha256=model_sha,
        model_fit_through_day="2026-10-31",
        winner_scores=scores or {str(i): 10.0 - i for i in range(1, 9)},
        outsider_scores=outsider_scores or {
            str(i): (15.0 if i == 6 else 1.0) for i in range(1, 9)
        },
    )


def sealed(items, *, salt=SALT, manifest=None):
    if manifest is None:
        manifest = {i.race_id: i.race_day for i in items}
    return seal_nar_prospective_batch(manifest, items, private_salt=salt)


def test_salted_hash_commitment_for_complete_future_prospective_batch():
    one = forecast()
    two = forecast(num=2)
    batch = sealed([one, two])
    assert batch.schema == "NarPrivateProspectiveCommitment.v1"
    assert len(batch.sha256_digest) == 64
    assert batch.registered_flat_races == batch.locked_forecasts == 2
    assert batch.missing_forecasts == 0
    assert batch.distinct_race_days == 1
    assert not batch.freeze_time_independently_verified
    assert not batch.prior_to_result_publication_proven
    assert not batch.actual_wagers_proven
    assert not batch.positive_expected_value_demonstrated
    assert not batch.protected_historical_holdout_opened
    verified = verify_nar_prospective_batch(
        batch, {one.race_id:one.race_day, two.race_id:two.race_day},
        [two, one], private_salt=SALT,
    )
    assert verified.sha256_matches_private_snapshot
    assert not verified.independently_timestamped_before_off
    assert not verified.legitimate_preoff_roster_verified
    assert not verified.authorized_for_realized_roi
    assert not verified.positive_expected_value_demonstrated
    assert "架空競馬場" not in repr(batch)


def test_digest_does_not_depend_on_manifest_or_score_dict_input_order():
    one = forecast()
    two = forecast(num=2)
    a = sealed([one, two])
    changed_order_one = replace(
        one,
        winner_scores=dict(reversed(list(one.winner_scores.items()))),
        outsider_scores=dict(reversed(list(one.outsider_scores.items()))),
    )
    b = sealed([two, changed_order_one])
    assert a.sha256_digest == b.sha256_digest


def test_modifying_score_roster_timestamp_or_model_changes_commitment():
    original = forecast()
    first = sealed([original])
    modifications = (
        replace(original, winner_scores={
            **original.winner_scores, "1": 9.25,
        }),
        replace(original, outsider_scores={
            **original.outsider_scores, "6": 3.75,
        }),
        replace(original, model_source_sha256="b"*64),
        replace(original, generated_at_utc=original.generated_at_utc + timedelta(minutes=1)),
        replace(original, roster_observed_at_utc=original.roster_observed_at_utc + timedelta(minutes=1)),
        replace(original, scheduled_off_utc=original.scheduled_off_utc + timedelta(minutes=1)),
    )
    for edited in modifications:
        assert not verify_nar_prospective_batch(
            first, {original.race_id:original.race_day},
            [edited], private_salt=SALT,
        ).sha256_matches_private_snapshot
    assert not verify_nar_prospective_batch(
        first, {original.race_id:original.race_day},
        [original], private_salt=b"X"*32,
    ).sha256_matches_private_snapshot


def test_nested_scores_are_immutable_after_original_caller_changes():
    original = {str(i): float(i) for i in range(1, 9)}
    obj = forecast(scores=original)
    first = sealed([obj])
    original["1"] = 900.0
    assert obj.winner_scores["1"] == 1.0
    assert sealed([obj]).sha256_digest == first.sha256_digest
    with pytest.raises(TypeError):
        obj.winner_scores["1"] = 100.0


def test_cannot_hide_dropped_race_or_duplicate_frozen_forecast():
    a = forecast()
    b = forecast(num=2)
    manifest = {a.race_id:a.race_day,b.race_id:b.race_day}
    with pytest.raises(ValueError, match="NAR_FORWARD_FULL_MANIFEST_REQUIRED"):
        sealed([a], manifest=manifest)
    with pytest.raises(ValueError, match="NAR_FORWARD_DUPLICATE_OR_UNREGISTERED_FORECAST"):
        sealed([a, a], manifest=manifest)
    wrong = forecast(num=3)
    with pytest.raises(ValueError, match="NAR_FORWARD_DUPLICATE_OR_UNREGISTERED_FORECAST"):
        sealed([a, wrong], manifest=manifest)
    with pytest.raises(ValueError, match="NAR_FORWARD_MODEL_VERSION_CHANGED_WITHIN_BATCH"):
        sealed([a, replace(b, model_source_sha256="b"*64)], manifest=manifest)


@pytest.mark.parametrize(("day", "fail"), [
    ("2025-01-15", "NAR_FORWARD_PROSPECTIVE_DAY_ONLY"),
    ("2024-11-14", "NAR_FORWARD_PROSPECTIVE_DAY_ONLY"),
    ("2026-11-01", "NAR_FORWARD_PROSPECTIVE_DAY_ONLY"),
])
def test_historical_and_protected_holdout_dates_never_allowed(day, fail):
    case = forecast(day=day)
    with pytest.raises(ValueError, match=fail):
        sealed([case])


@pytest.mark.parametrize("offset", [
    timedelta(0), timedelta(minutes=1),
])
def test_forecast_at_or_after_race_off_refused(offset):
    p = forecast()
    future = replace(
        p, generated_at_utc=p.scheduled_off_utc + offset,
    )
    with pytest.raises(ValueError, match="NAR_FORWARD_PREOFF_CLOCK_SEQUENCE_INVALID"):
        sealed([future])


def test_altered_roster_or_invalid_score_fails_without_opening_results():
    p = forecast()
    new_scores = dict(p.outsider_scores)
    new_scores.pop("7")
    with pytest.raises(ValueError, match="NAR_FORWARD_SCORE_ROSTERS_DIFFER"):
        sealed([replace(p, outsider_scores=new_scores)])
    with pytest.raises(ValueError, match="NAR_FORWARD_INVALID_SCORE"):
        sealed([replace(p, winner_scores={**p.winner_scores, "1": float("nan")})])
    with pytest.raises(ValueError, match="NAR_FORWARD_INVALID_SCORE"):
        sealed([replace(p, winner_scores={**p.winner_scores, "1": True})])
    with pytest.raises(ValueError, match="NAR_FORWARD_ALL_ZERO_SCORES"):
        sealed([replace(p, winner_scores={k: 0.0 for k in p.winner_scores})])


def test_generation_order_and_lineage_fail_closed():
    p = forecast()
    with pytest.raises(ValueError, match="NAR_FORWARD_PREOFF_CLOCK_SEQUENCE_INVALID"):
        sealed([replace(p, roster_observed_at_utc=p.generated_at_utc + timedelta(seconds=1))])
    with pytest.raises(ValueError, match="NAR_FORWARD_PREOFF_CLOCK_SEQUENCE_INVALID"):
        sealed([replace(p, generated_at_utc=p.scheduled_off_utc - timedelta(days=8))])
    with pytest.raises(ValueError, match="NAR_FORWARD_MODEL_LINEAGE_INVALID"):
        sealed([replace(p, model_source_sha256="tampered")])
    with pytest.raises(ValueError, match="NAR_FORWARD_MODEL_LINEAGE_INVALID"):
        sealed([replace(p, model_fit_through_day=p.race_day)])
    with pytest.raises(ValueError, match="NAR_FORWARD_MODEL_LINEAGE_INVALID"):
        sealed([replace(p, model_fit_through_day="2026-11-13")])
    with pytest.raises(ValueError, match="NAR_FORWARD_MODEL_LINEAGE_INVALID"):
        sealed([replace(p, model_fit_through_day="2026-11-14")])
    with pytest.raises(ValueError, match="NAR_FORWARD_ODDS_FREE_SELECTION_REQUIRED"):
        sealed([replace(p, market_odds_in_selection=True)])


def test_private_salt_and_tampered_public_receipt_rejected():
    p=forecast()
    with pytest.raises(ValueError, match="NAR_FORWARD_STRONG_PRIVATE_SALT_REQUIRED"):
        sealed([p], salt=b"weak")
    proof=sealed([p])
    for forbidden in (
        "freeze_time_independently_verified",
        "prior_to_result_publication_proven",
        "source_rights_verified",
        "actual_wagers_proven",
        "positive_expected_value_demonstrated",
        "protected_historical_holdout_opened",
        "predicted_races_contain_final_outcomes",
    ):
        corrupted=replace(proof, **{forbidden:True})
        with pytest.raises(ValueError, match="NAR_FORWARD_COMMITMENT_CONTRACT_INVALID"):
            verify_nar_prospective_batch(
                corrupted, {p.race_id: p.race_day}, [p], private_salt=SALT,
            )
    with pytest.raises(ValueError, match="NAR_FORWARD_COMMITMENT_CONTRACT_INVALID"):
        verify_nar_prospective_batch(
            replace(proof, distinct_race_days=999),
            {p.race_id: p.race_day}, [p], private_salt=SALT,
        )


def test_manipulated_race_day_and_off_time_cannot_be_valid_commitment():
    p = forecast()
    with pytest.raises(ValueError, match="NAR_FORWARD_MANIFEST_RACE_DAY_MISMATCH"):
        sealed([replace(p, race_day="2026-11-15")])
    with pytest.raises(ValueError, match="NAR_FORWARD_PREOFF_CLOCK_SEQUENCE_INVALID"):
        sealed([replace(p, scheduled_off_utc=p.scheduled_off_utc + timedelta(days=1))])
