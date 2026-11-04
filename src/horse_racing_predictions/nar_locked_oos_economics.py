"""NAR-only locked 2023-24 out-of-sample economic research: no public claims.

Pure, offline in-memory evaluation of independently frozen pre-off candidate
and benchmark predictions against later official settlement candidates.
Does not acquire data, authenticate source rights, train/refit, post, wager,
or inspect protected 2025+ records. All source material must already have
passed a separate operator-approved provenance and timestamp review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta, timezone
from math import isfinite
import random
import re
from typing import Mapping, Sequence

from .oddsfree_ev_research import (
    FinalRaceSettlement, FrozenOddsFreeForecast,
    _race_result, select_top3_and_outsider,
)

_FIRST = date(2023, 1, 1)
_LAST = date(2024, 12, 31)
_FIT_END = date(2022, 12, 31)
_MIN_RACES = 500
_MIN_DAYS = 60
# Fixed pre-outcome coverage floor: missing settlements must not be discarded
# until an apparently profitable 500-race subset remains.
_MIN_COVERAGE_NUMERATOR = 19
_MIN_COVERAGE_DENOMINATOR = 20
_NAR_ID = re.compile(r"NAR:([0-9]{8}):([^:/\\\r\n]{1,40}):([0-9]{2})\Z")
_REASONS = frozenset({
    "pre_event_snapshot_missing",
    "unverified_official_payout",
    "incomplete_field_or_results",
    "scratch_or_refund",
    "dead_heat",
    "unsupported_field_size",
    "outside_predeclared_flat_scope",
})


@dataclass(frozen=True)
class NarLockedOutOfSample:
    status: str
    scheduled_races: int
    paired_settled_races: int
    excluded_races: int
    exclusions_by_reason: tuple[tuple[str, int], ...]
    racing_days: int
    in_scope_manifest_races: int
    eligible_race_coverage_fraction: float
    minimum_screening_covered: bool
    minimum_coverage_met: bool
    economic_diagnostic_performed: bool
    candidate_realized_roi: float | None
    benchmark_realized_roi: float | None
    matched_improvement_roi: float | None
    candidate_cost_adjusted_roi: float | None
    candidate_day_block_lower_95: float | None
    matched_improvement_day_block_lower_95: float | None
    bootstrap_days: int
    additional_cost_yen_per_race: int
    observed_source_rights_independently_verified: bool = False
    observed_pre_event_freeze_independently_verified: bool = False
    official_payout_provenance_verified: bool = False
    protected_2025_plus_opened: bool = False
    positive_expected_value_demonstrated: bool = False
    authorized_for_note: bool = False
    authorized_for_betting: bool = False


def _day(text: str) -> date:
    if not isinstance(text, str):
        raise ValueError("NAR_OOS_NONCANONICAL_DAY")
    try:
        d = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("NAR_OOS_NONCANONICAL_DAY") from exc
    if d.isoformat() != text:
        raise ValueError("NAR_OOS_NONCANONICAL_DAY")
    return d


def _quantile(items: list[float], fraction: float) -> float:
    idx = (len(items) - 1) * fraction
    i = int(idx)
    j = min(i + 1, len(items)-1)
    return items[i] + (items[j] - items[i]) * (idx - i)


def _validate_frozen(
    rows: Sequence[FrozenOddsFreeForecast],
    calendar: Mapping[str, date],
    excluded: Mapping[str, str],
    designation: str,
) -> dict[str, FrozenOddsFreeForecast]:
    seen: dict[str, FrozenOddsFreeForecast] = {}
    model_fingerprints = set()
    for f in rows:
        if not isinstance(f, FrozenOddsFreeForecast):
            raise ValueError("NAR_OOS_FROZEN_FORECAST_REQUIRED")
        if f.race_id not in calendar:
            raise ValueError("NAR_OOS_UNDECLARED_FORECAST")
        if f.race_id in seen:
            raise ValueError("NAR_OOS_DUPLICATE_FORECAST")
        if f.race_id in excluded:
            raise ValueError("NAR_OOS_EXCLUDED_RACE_IN_FORECAST")
        day = calendar[f.race_id]
        if _day(f.race_day) != day:
            raise ValueError("NAR_OOS_RACE_DAY_MISMATCH")
        # The shared frozen selection contract also rejects all 2025+,
        # post-off forecasts, odds selection and invalid field score maps.
        select_top3_and_outsider(f)
        issued = f.predicted_at_utc.astimezone(timezone(timedelta(hours=9)))
        off = f.post_time_utc.astimezone(timezone(timedelta(hours=9)))
        if (off.date() != day or issued.date() > day
                or issued.date() < day-timedelta(days=7)
                or not issued < off):
            raise ValueError("NAR_OOS_PRE_OFF_TIME_INVALID")
        if _day(f.model_fit_through_day) > _FIT_END:
            raise ValueError("NAR_OOS_2022_MODEL_LOCK_BROKEN")
        seen[f.race_id] = f
        model_fingerprints.add((f.model_ref, f.model_fit_through_day))
    if len(model_fingerprints) != 1 and seen:
        raise ValueError("NAR_OOS_SINGLE_FROZEN_MODEL_REQUIRED")
    return seen


def evaluate_nar_locked_out_of_sample(
    *,
    expected_races: Mapping[str, str],
    candidate_forecasts: Sequence[FrozenOddsFreeForecast],
    benchmark_forecasts: Sequence[FrozenOddsFreeForecast],
    settlements: Sequence[FinalRaceSettlement],
    documented_exclusions: Mapping[str, str],
    extra_cost_yen_per_race: int = 0,
    bootstrap_samples: int = 1000,
) -> NarLockedOutOfSample:
    """Reject selective omission; compare paired date-block profitability.

    Note: even a statistically positive result does not establish *actual*
    EV without external source rights, source provenance, pre-event capture
    evidence, untampered unseen outcomes and model selection audit. The
    result is unpromotable diagnostics only.
    """
    if (not isinstance(expected_races, Mapping)
            or not isinstance(documented_exclusions, Mapping)
            or any(not isinstance(s, (tuple, list)) for s in (
                candidate_forecasts, benchmark_forecasts, settlements,
            ))
            or not 1 <= len(expected_races) <= 20000
            or any(len(s) > 2*len(expected_races) for s in (
                candidate_forecasts, benchmark_forecasts, settlements,
            ))
            or type(extra_cost_yen_per_race) is not int
            or not 0 <= extra_cost_yen_per_race <= 100
            or type(bootstrap_samples) is not int
            or not 200 <= bootstrap_samples <= 5000):
        raise ValueError("NAR_OOS_BOUNDED_STUDY_INPUT_REQUIRED")
    calendar: dict[str, date] = {}
    for rid, d in expected_races.items():
        if not isinstance(rid, str) or not (m := _NAR_ID.fullmatch(rid)):
            raise ValueError("NAR_OOS_CANONICAL_RACE_ID_REQUIRED")
        day = _day(d)
        if (not _FIRST <= day <= _LAST
                or m.group(1) != day.strftime("%Y%m%d")
                or not 1 <= int(m.group(3)) <= 20):
            raise ValueError("NAR_OOS_LOCKED_CALENDAR_MISMATCH")
        calendar[rid] = day
    if (not all(isinstance(k, str) and isinstance(v, str)
                for k, v in documented_exclusions.items())
            or not set(documented_exclusions).issubset(calendar)
            or not set(documented_exclusions.values()).issubset(_REASONS)):
        raise ValueError("NAR_OOS_UNREGISTERED_EXCLUSION_REASON")
    candidate = _validate_frozen(
        candidate_forecasts, calendar, documented_exclusions, "candidate",
    )
    benchmark = _validate_frozen(
        benchmark_forecasts, calendar, documented_exclusions, "benchmark",
    )
    finals: dict[str, FinalRaceSettlement] = {}
    for result in settlements:
        if not isinstance(result, FinalRaceSettlement):
            raise ValueError("NAR_OOS_SETTLEMENT_OBJECT_REQUIRED")
        if result.race_id not in calendar:
            raise ValueError("NAR_OOS_UNDECLARED_SETTLEMENT")
        if result.race_id in finals:
            raise ValueError("NAR_OOS_DUPLICATE_SETTLEMENT")
        if result.race_id in documented_exclusions:
            raise ValueError("NAR_OOS_EXCLUDED_RACE_HAS_SETTLEMENT")
        finals[result.race_id] = result
    eligible = set(calendar)-set(documented_exclusions)
    if set(candidate) != eligible or set(benchmark) != eligible or set(finals) != eligible:
        raise ValueError("NAR_OOS_MISSING_OR_SELECTIVELY_OMITTED_RACE")
    if eligible:
        ids_candidate = {f.model_ref for f in candidate.values()}
        ids_baseline = {f.model_ref for f in benchmark.values()}
        if ids_candidate == ids_baseline:
            raise ValueError("NAR_OOS_BENCHMARK_MUST_BE_SEPARATELY_IDENTIFIED")
    for rid in eligible:
        a,b= candidate[rid], benchmark[rid]
        if (a.race_day != b.race_day or a.post_time_utc != b.post_time_utc
                or a.predicted_at_utc != b.predicted_at_utc
                or set(a.winner_scores) != set(b.winner_scores)
                or set(a.winner_scores) != set(finals[rid].finishing_positions)):
            raise ValueError("NAR_OOS_BENCHMARK_OR_SETTLEMENT_FIELD_MISMATCH")

    # Validate the full paired settlement arithmetic on EVERY admitted race,
    # even when the sample is underpowered and no ROI may be returned.
    # Otherwise a corrupt or outcome-inconsistent small real-data upload
    # could misleadingly be labelled a structurally eligible sample.
    blocks: dict[date, list[tuple[int, int]]] = {}
    for rid in sorted(eligible):
        final = finals[rid]
        candidate_return = _race_result(
            select_top3_and_outsider(candidate[rid]), final,
        )
        benchmark_return = _race_result(
            select_top3_and_outsider(benchmark[rid]), final,
        )
        blocks.setdefault(calendar[rid], []).append(
            (candidate_return[0] + candidate_return[1],
             benchmark_return[0] + benchmark_return[1]),
        )

    days = len({calendar[r] for r in eligible})
    by_reason = tuple(sorted(
        (reason, sum(v == reason for v in documented_exclusions.values()))
        for reason in set(documented_exclusions.values())
    ))
    sample_minimum_met = len(eligible) >= _MIN_RACES and days >= _MIN_DAYS
    predeclared_scope = sum(
        code == "outside_predeclared_flat_scope"
        for code in documented_exclusions.values()
    )
    in_scope = len(calendar) - predeclared_scope
    coverage_fraction = len(eligible) / in_scope if in_scope else 0.0
    # Use exact integer arithmetic so 95% is not sensitive to floating
    # rounding. Exclusions outside the preregistered flat-race scope are
    # counted in the calendar but not the coverage denominator.
    coverage_met = (
        in_scope > 0
        and _MIN_COVERAGE_DENOMINATOR * len(eligible)
        >= _MIN_COVERAGE_NUMERATOR * in_scope
    )
    min_pass = sample_minimum_met and coverage_met
    common = dict(
        scheduled_races=len(calendar), paired_settled_races=len(eligible),
        excluded_races=len(documented_exclusions),
        exclusions_by_reason=by_reason,
        racing_days=days, minimum_screening_covered=min_pass,
        minimum_coverage_met=coverage_met,
        in_scope_manifest_races=in_scope,
        eligible_race_coverage_fraction=coverage_fraction,
        bootstrap_days=days, additional_cost_yen_per_race=extra_cost_yen_per_race,
    )
    if not min_pass:
        return NarLockedOutOfSample(
            status=(
                "NAR_OOS_INSUFFICIENT_PAIRED_COVERAGE"
                if sample_minimum_met and not coverage_met
                else "NAR_OOS_INSUFFICIENT_PREREGISTERED_EVIDENCE"
            ),
            economic_diagnostic_performed=False,
            candidate_realized_roi=None, benchmark_realized_roi=None,
            matched_improvement_roi=None, candidate_cost_adjusted_roi=None,
            candidate_day_block_lower_95=None,
            matched_improvement_day_block_lower_95=None,
            **common,
        )

    # Payout pairs already passed strict validation above; this branch
    # only computes aggregate ROI after both minimum size gates pass.
    spend = (200+extra_cost_yen_per_race) * len(eligible)
    total_a=sum(x for day_rows in blocks.values() for x,_ in day_rows)
    total_b=sum(y for day_rows in blocks.values() for _,y in day_rows)
    candidate_roi=total_a/(200*len(eligible))-1
    bench_roi=total_b/(200*len(eligible))-1
    adjusted_roi=total_a/spend-1
    delta_roi=(total_a-total_b)/spend

    # Bootstrap WHOLE matched race days; both model outcomes use precisely
    # the same sampled days, correcting race-within-day dependence.
    daily=[(sum(x for x,_ in v), sum(y for _,y in v),len(v))
           for _,v in sorted(blocks.items())]
    rng=random.Random(20261103)
    sample_roi=[]
    sample_delta=[]
    for _ in range(bootstrap_samples):
        a_total=b_total=sampled_races=0
        for _ in range(len(daily)):
            a,b,n = daily[rng.randrange(len(daily))]
            a_total+=a
            b_total+=b
            sampled_races+=n
        sample_roi.append(a_total/((200+extra_cost_yen_per_race)*sampled_races)-1)
        sample_delta.append((a_total-b_total)/((200+extra_cost_yen_per_race)*sampled_races))
    sample_roi.sort()
    sample_delta.sort()
    lower=_quantile(sample_roi,0.025)
    delta_lower=_quantile(sample_delta,0.025)
    if not all(isfinite(v) for v in (
        candidate_roi,bench_roi,adjusted_roi,delta_roi,lower,delta_lower,
    )):
        raise ValueError("NAR_OOS_NONFINITE_ECONOMIC_DIAGNOSTIC")
    return NarLockedOutOfSample(
        status="NAR_OOS_DIAGNOSTIC_ONLY_RIGHTS_TIMESTAMPS_AND_FORWARD_TEST_UNVERIFIED",
        economic_diagnostic_performed=True,
        candidate_realized_roi=candidate_roi,
        benchmark_realized_roi=bench_roi,
        matched_improvement_roi=delta_roi,
        candidate_cost_adjusted_roi=adjusted_roi,
        candidate_day_block_lower_95=lower,
        matched_improvement_day_block_lower_95=delta_lower,
        **common,
    )
