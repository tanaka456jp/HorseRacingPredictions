"""Synthetic-only preregistered Friday OOS candidate admission tests."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from horse_racing_predictions.friday_oos_admission import (
    audit_preregistered_friday_oos, evaluate_preregistered_friday_oos,
)
from horse_racing_predictions.oddsfree_ev_research import (
    FinalRaceSettlement, FrozenOddsFreeForecast,
)

JST = timezone(timedelta(hours=9))


def _case(race_day="2024-10-26", race_num=1):
    day = date.fromisoformat(race_day)
    friday = day - timedelta(days=day.weekday() - 4)
    rid = f"JRA-{day.strftime('%Y%m%d')}-{race_num:02d}"
    horses = [f"FICTIONAL_{x}" for x in range(1, 9)]
    event = datetime(day.year, day.month, day.day, 14, 0, tzinfo=JST)
    frozen = datetime(friday.year, friday.month, friday.day, 14, 0, tzinfo=JST)
    forecast = FrozenOddsFreeForecast(
        race_id=rid, race_day=race_day,
        predicted_at_utc=frozen.astimezone(timezone.utc),
        post_time_utc=event.astimezone(timezone.utc),
        model_ref="FICTIONAL_2022_FROZEN",
        model_fit_through_day="2022-12-31",
        winner_scores={h: 10.0-i for i, h in enumerate(horses)},
        outsider_scores={h: 2.0 if i == 3 else 1.0 for i, h in enumerate(horses)},
    )
    settlement = FinalRaceSettlement(
        race_id=rid,
        finishing_positions={h: i + 1 for i, h in enumerate(horses)},
        win_return_per_100_yen={h: 300 if i == 0 else 0
                                for i, h in enumerate(horses)},
        place_return_per_100_yen={h: 130 if i < 3 else 0
                                  for i, h in enumerate(horses)},
    )
    return rid, forecast, settlement


def _audit(cases, **kw):
    return audit_preregistered_friday_oos(
        expected_races=kw.get("expected_races", {rid: f.race_day for rid, f, _ in cases}),
        forecasts=kw.get("forecasts", [f for _, f, _ in cases]),
        settlements=kw.get("settlements", [s for _, _, s in cases]),
        documented_exclusions=kw.get("documented_exclusions", {}),
    )


def test_genuine_saturday_sunday_friday_snapshots_admitted_without_ev_claim():
    a = _case("2024-10-26", 1)
    b = _case("2024-10-27", 2)
    result = _audit([a, b])
    assert result.scheduled_races == 2
    assert result.frozen_forecasts == 2
    assert result.distinct_racing_dates == 2
    assert result.status == "INSUFFICIENT_LOCKED_OOS_SAMPLE"
    assert not result.meets_preregistered_sample_minimums
    assert not result.positive_expected_value_demonstrated
    assert not result.training_source_rights_verified
    assert not result.publication_authorized


@pytest.mark.parametrize("when", [
    datetime(2024, 10, 26, 11, tzinfo=JST),  # Saturday race-day preview
    datetime(2024, 10, 25, 11, tzinfo=JST),  # Before Friday noon evidence
    datetime(2024, 10, 24, 14, tzinfo=JST),  # Thursday, not Friday freeze
    datetime(2024, 10, 26, 14, tzinfo=JST),  # Exactly race off
])
def test_late_early_or_not_friday_predictions_are_rejected(when):
    c = _case()
    tampered = replace(c[1], predicted_at_utc=when)
    with pytest.raises(ValueError, match="FRIDAY_OOS_GENUINE_FRIDAY_FREEZE_REQUIRED"):
        _audit([c], forecasts=[tampered])


def test_model_fit_must_respect_frozen_2022_selection_period():
    c = _case()
    f = replace(c[1], model_fit_through_day="2024-10-24")
    with pytest.raises(ValueError, match="FRIDAY_OOS_MODEL_FIT_OUTSIDE_FROZEN_FOLD"):
        _audit([c], forecasts=[f])


def test_missing_settlement_cannot_be_hidden_after_bad_prediction():
    c = _case()
    with pytest.raises(ValueError, match="FRIDAY_OOS_MISSING_OR_SELECTIVELY_DROPPED_RACE"):
        _audit([c], settlements=[])


def test_complete_calendar_must_account_for_every_race():
    c1, c2 = _case(race_num=1), _case(race_num=2)
    manifest = {c1[0]: c1[1].race_day, c2[0]: c2[1].race_day}
    with pytest.raises(ValueError, match="FRIDAY_OOS_MISSING_OR_SELECTIVELY_DROPPED_RACE"):
        _audit([c1], expected_races=manifest)
    status = _audit([c1], expected_races=manifest,
                    documented_exclusions={c2[0]: "refund_or_scratch"})
    assert status.scheduled_races == 2
    assert status.documented_exclusions == 1
    assert status.excluded_by_reason == (("refund_or_scratch", 1),)


def test_cannot_claim_discretionary_exclusions_or_remove_bad_race_after_settlement():
    c = _case()
    with pytest.raises(ValueError, match="FRIDAY_OOS_UNREGISTERED_EXCLUSION"):
        _audit([], expected_races={c[0]: c[1].race_day},
               documented_exclusions={c[0]: "not_profitable"})
    with pytest.raises(ValueError, match="FRIDAY_OOS_EXCLUDED_RACE_HAS_FORECAST"):
        _audit([c], documented_exclusions={c[0]: "dead_heat"})


def test_2025_final_holdout_and_weekday_races_not_admitted():
    c = _case("2024-10-26")
    with pytest.raises(ValueError, match="FRIDAY_OOS_OUTSIDE_LOCKED_WEEKEND_FOLD"):
        _audit([], expected_races={"JRA-20250104-01": "2025-01-04"},
               documented_exclusions={"JRA-20250104-01": "refund_or_scratch"})
    with pytest.raises(ValueError, match="FRIDAY_OOS_OUTSIDE_LOCKED_WEEKEND_FOLD"):
        _audit([], expected_races={"JRA-20241028-01": "2024-10-28"},
               documented_exclusions={"JRA-20241028-01": "refund_or_scratch"})
    with pytest.raises(ValueError, match="FRIDAY_OOS_RACE_DATE_MISMATCH"):
        _audit([c], expected_races={c[0]: "2024-10-27"})


def test_duplicate_forecasts_and_unregistered_settlements_rejected():
    c = _case()
    with pytest.raises(ValueError, match="FRIDAY_OOS_DUPLICATE_FORECAST"):
        _audit([c], forecasts=[c[1], c[1]])
    unknown = replace(c[2], race_id="JRA-20241026-99")
    with pytest.raises(ValueError, match="FRIDAY_OOS_UNDECLARED_SETTLEMENT_RACE"):
        _audit([c], settlements=[unknown])


def test_report_never_uses_economic_outcomes_or_promotes_to_note():
    c = _case()
    first = _audit([c])
    huge_payouts = replace(c[2], win_return_per_100_yen={
        k: 1000000 for k in c[2].win_return_per_100_yen
    })
    second = _audit([(c[0], c[1], huge_payouts)])
    assert first == second
    assert not second.payout_rights_verified
    assert not second.historical_friday_availability_independently_verified


def test_exact_preregistered_500_races_60_days_is_only_structural_gate():
    start = date(2023, 1, 7)  # Saturday
    all_cases = []
    for week in range(60):
        day = start + timedelta(days=7 * week)
        # 20 dates x 9 races + 40 dates x 8 races = 500 races
        # spread over exactly 60 distinct race dates.
        for race_num in range(1, 10 if week < 20 else 9):
            all_cases.append(_case(day.isoformat(), race_num))
    assert len(all_cases) == 500
    result = _audit(all_cases)
    assert result.scheduled_races == 500
    assert result.distinct_racing_dates == 60
    assert result.meets_preregistered_sample_minimums
    assert result.status == "STRUCTURAL_SAMPLE_MINIMUMS_MET_EXTERNAL_EVIDENCE_REQUIRED"
    assert not result.manifest_independently_verified
    assert not result.positive_expected_value_demonstrated
    assert not result.publication_authorized
    assert not result.training_source_rights_verified


def test_500_races_on_fewer_than_60_days_cannot_pass_sample_gate():
    start = date(2023, 1, 7)
    all_cases = [
        _case((start + timedelta(days=7 * week)).isoformat(), race_num)
        for week in range(50) for race_num in range(1, 11)
    ]
    result = _audit(all_cases)
    assert result.frozen_forecasts == 500
    assert result.distinct_racing_dates == 50
    assert not result.meets_preregistered_sample_minimums
    assert result.status == "INSUFFICIENT_LOCKED_OOS_SAMPLE"


def _qualifying_fictional_calendar():
    first = date(2023, 1, 7)
    return [
        _case((first + timedelta(days=7 * week)).isoformat(), race_num)
        for week in range(60)
        for race_num in range(1, 10 if week < 20 else 9)
    ]


def _economic(cases, *, expected_races=None, documented_exclusions=None):
    return evaluate_preregistered_friday_oos(
        expected_races=(
            {rid: f.race_day for rid, f, _ in cases}
            if expected_races is None else expected_races
        ),
        forecasts=[f for _, f, _ in cases],
        settlements=[p for _, _, p in cases],
        documented_exclusions=(
            {} if documented_exclusions is None else documented_exclusions
        ),
        bootstrap_samples=200,
    )


def test_locked_friday_roi_cannot_run_on_underpowered_two_race_sample():
    result = _economic([_case("2024-10-26", 1), _case("2024-10-27", 2)])
    assert result.status == "BLOCKED_INSUFFICIENT_PREREGISTERED_OOS_SAMPLE"
    assert result.economics is None
    assert result.economic_evaluation_performed is False
    assert result.positive_expected_value_demonstrated is False
    assert result.publication_authorized is False


def test_locked_friday_roi_only_diagnostic_after_complete_500_race_60_day_gate():
    races = _qualifying_fictional_calendar()
    assert len(races) == 500
    report = _economic(races)
    assert report.economic_evaluation_performed
    assert report.admission.meets_preregistered_sample_minimums
    assert report.admission.distinct_racing_dates == 60
    assert report.economics is not None
    assert report.economics.races == 500
    assert report.economics.independent_race_days == 60
    assert report.economics.bootstrap_interval_available
    assert report.status == "HISTORICAL_REALIZED_ROI_DIAGNOSTIC_UNVERIFIED_PROVENANCE"
    # All bets win in this fabricated example, but no false EV claim follows.
    assert report.economics.combined_realized_roi > 0
    assert not report.positive_expected_value_demonstrated
    assert not report.economics.positive_expected_value_demonstrated
    assert not report.publication_authorized
    assert not report.live_betting_authorized
    assert not report.admission.training_source_rights_verified


def test_locked_economic_evaluator_blocks_missing_and_invalid_payouts():
    cases = _qualifying_fictional_calendar()
    expected = {rid: f.race_day for rid, f, _ in cases}
    with pytest.raises(ValueError, match="FRIDAY_OOS_MISSING_OR_SELECTIVELY_DROPPED_RACE"):
        _economic(cases[:-1], expected_races=expected)
    rid, frozen, settlement = cases[-1]
    invalid = replace(settlement, win_return_per_100_yen={
        k: 0 for k in settlement.win_return_per_100_yen
    })
    with pytest.raises(ValueError, match="PAYOUT_CONTRADICTS_FINAL_FINISH"):
        _economic([*cases[:-1], (rid, frozen, invalid)])
