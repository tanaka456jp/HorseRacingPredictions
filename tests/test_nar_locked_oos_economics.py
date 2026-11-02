"""Fictional NAR locked OOS paired-payout regression tests; no source I/O."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import pytest
from horse_racing_predictions.nar_locked_oos_economics import evaluate_nar_locked_out_of_sample
from horse_racing_predictions.oddsfree_ev_research import (
    FrozenOddsFreeForecast, FinalRaceSettlement,
)

JST = timezone(timedelta(hours=9))


def race(day_text="2023-01-07", race_num=1):
    day=date.fromisoformat(day_text)
    rid=f"NAR:{day:%Y%m%d}:架空競馬場:{race_num:02d}"
    off=datetime(day.year,day.month,day.day,15,tzinfo=JST)
    freeze=off-timedelta(hours=3)
    horses=[str(n) for n in range(1,9)]
    def build(model, winners, outsider):
        return FrozenOddsFreeForecast(
            race_id=rid,race_day=day_text,post_time_utc=off,
            predicted_at_utc=freeze,model_ref=model,
            model_fit_through_day="2022-12-31",
            winner_scores={h:float(winners.get(h,0.5)) for h in horses},
            outsider_scores={h:(10. if h==outsider else 1.) for h in horses},
        )
    candidate=build("FICTIONAL_CANDIDATE",{"1":9,"2":8,"4":7},"3")
    benchmark=build("FICTIONAL_BENCHMARK",{"4":9,"5":8,"6":7},"8")
    final=FinalRaceSettlement(
        race_id=rid,
        finishing_positions={h:i+1 for i,h in enumerate(horses)},
        win_return_per_100_yen={h:(300 if h=="1" else 0) for h in horses},
        place_return_per_100_yen={h:(130 if h in {"1","2","3"} else 0)
                                   for h in horses},
    )
    return rid,candidate,benchmark,final


def run(cases,*,calendar=None,excluded=None,candidates=None,benchmarks=None,
        settlements=None,cost=0):
    return evaluate_nar_locked_out_of_sample(
        expected_races={r:f.race_day for r,f,_,_ in cases} if calendar is None else calendar,
        candidate_forecasts=[f for _,f,_,_ in cases] if candidates is None else candidates,
        benchmark_forecasts=[b for _,_,b,_ in cases] if benchmarks is None else benchmarks,
        settlements=[s for _,_,_,s in cases] if settlements is None else settlements,
        documented_exclusions={} if excluded is None else excluded,
        extra_cost_yen_per_race=cost,bootstrap_samples=200,
    )


def calendar_500(days=60):
    start=date(2023,1,7)
    if days==60:
        return [race((start+timedelta(days=7*w)).isoformat(),i)
                for w in range(60) for i in range(1,10 if w<20 else 9)]
    return [race((start+timedelta(days=7*w)).isoformat(),i)
            for w in range(50) for i in range(1,11)]


def test_500_races_60_days_matched_pair_positive_fictional_returns_not_ev():
    cases=calendar_500()
    assert len(cases)==500
    result=run(cases,cost=50)
    assert result.paired_settled_races==500
    assert result.racing_days==60
    assert result.minimum_screening_covered
    assert result.economic_diagnostic_performed
    assert result.candidate_realized_roi==pytest.approx(1.15)
    assert result.benchmark_realized_roi==pytest.approx(-1)
    assert result.matched_improvement_roi==pytest.approx(2.15)
    assert result.candidate_cost_adjusted_roi==pytest.approx(.72)
    assert result.candidate_day_block_lower_95==pytest.approx(.72)
    assert result.matched_improvement_day_block_lower_95==pytest.approx(2.15)
    assert not result.positive_expected_value_demonstrated
    assert not result.observed_source_rights_independently_verified
    assert not result.official_payout_provenance_verified
    assert not result.observed_pre_event_freeze_independently_verified
    assert not result.authorized_for_note
    assert not result.authorized_for_betting


def test_500_races_50_days_do_not_unlock_roi_or_ci():
    result=run(calendar_500(50))
    assert result.paired_settled_races==500
    assert result.racing_days==50
    assert not result.minimum_screening_covered
    assert not result.economic_diagnostic_performed
    assert result.candidate_realized_roi is None
    assert result.candidate_day_block_lower_95 is None


def test_omissions_must_be_explained_before_any_economic_comparison():
    one,two=race(race_num=1),race(race_num=2)
    expected={one[0]:one[1].race_day,two[0]:two[1].race_day}
    with pytest.raises(ValueError,match="NAR_OOS_MISSING_OR_SELECTIVELY_OMITTED_RACE"):
        run([one],calendar=expected)
    admitted=run([one],calendar=expected,excluded={two[0]:"scratch_or_refund"})
    assert admitted.scheduled_races==2
    assert admitted.excluded_races==1
    assert admitted.exclusions_by_reason==(("scratch_or_refund",1),)
    with pytest.raises(ValueError,match="NAR_OOS_UNREGISTERED_EXCLUSION_REASON"):
        run([one],calendar=expected,excluded={two[0]:"poor_profitability"})


def test_2025_heldout_date_and_malformed_source_race_key_are_rejected():
    with pytest.raises(ValueError,match="NAR_OOS_LOCKED_CALENDAR_MISMATCH"):
        run([],calendar={"NAR:20250101:架空競馬場:01":"2025-01-01"},
            excluded={"NAR:20250101:架空競馬場:01":"dead_heat"})
    x=race()
    with pytest.raises(ValueError,match="NAR_OOS_LOCKED_CALENDAR_MISMATCH"):
        run([],calendar={x[0]:"2023-01-08"},excluded={x[0]:"dead_heat"})
    with pytest.raises(ValueError,match="NAR_OOS_CANONICAL_RACE_ID_REQUIRED"):
        run([],calendar={"UNVERIFIED":"2023-01-07"},
            excluded={"UNVERIFIED":"dead_heat"})


def test_post_off_and_later_fit_cannot_enter_locked_assessment():
    x=race()
    with pytest.raises(ValueError,match="FORECAST_MUST_PRECEDE_RACE_OFF"):
        run([x],candidates=[replace(
            x[1],predicted_at_utc=x[1].post_time_utc,
        )])
    with pytest.raises(ValueError,match="NAR_OOS_2022_MODEL_LOCK_BROKEN"):
        run([x],candidates=[replace(
            x[1],model_fit_through_day="2023-01-06",
        )])
    with pytest.raises(ValueError,match="NAR_OOS_PRE_OFF_TIME_INVALID"):
        run([x],candidates=[replace(
            x[1],predicted_at_utc=x[1].predicted_at_utc-timedelta(days=30),
        )])


def test_benchmark_must_be_separate_and_cover_exact_matching_runner_field():
    x=race()
    with pytest.raises(ValueError,match="NAR_OOS_BENCHMARK_MUST_BE_SEPARATELY_IDENTIFIED"):
        run([x],benchmarks=[replace(x[2],model_ref=x[1].model_ref)])
    with pytest.raises(ValueError,match="NAR_OOS_BENCHMARK_OR_SETTLEMENT_FIELD_MISMATCH"):
        run([x],benchmarks=[replace(x[2],
            post_time_utc=x[2].post_time_utc+timedelta(minutes=1),
        )])


def test_matched_economic_payout_must_agree_with_actual_finish():
    all_races=calendar_500()
    rid,f,b,outcome=all_races[-1]
    broken=replace(outcome,win_return_per_100_yen={
        h:0 for h in outcome.win_return_per_100_yen
    })
    with pytest.raises(ValueError,match="PAYOUT_CONTRADICTS_FINAL_FINISH"):
        run([*all_races[:-1],(rid,f,b,broken)])


def test_duplicate_forecast_and_cost_guards():
    x=race()
    with pytest.raises(ValueError,match="NAR_OOS_DUPLICATE_FORECAST"):
        run([x],candidates=[x[1],x[1]])
    with pytest.raises(ValueError,match="NAR_OOS_BOUNDED_STUDY_INPUT_REQUIRED"):
        run([x],cost=101)
