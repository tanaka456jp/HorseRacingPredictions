"""Chronological, status-aware NAR form diagnostics from PRIVATE past results.

All historical form depends on earlier race DATES only, not earlier races
within the current date. Scratches/exclusions do NOT add starts. DNFs do
add starts, but never an invented numeric finishing rank. The completed
race's labels and statuses are private training targets, NEVER predictors.

A missing official outcome in any source month blocks readiness, even
when many individually complete races are available. No source access,
model fitting, OOS evaluation, betting, upload or publication.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Mapping

from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import RaceKey
from .nar_prior_day_features import NarAsOfFeatures, _birthday
from .nar_status_aware_training_labels import (
    NarHistoricalOutcomeLabel, NarPostEventLabelBatch,
)

Identity = tuple[str, str]
EntrantKey = tuple[RaceKey, int]


@dataclass(frozen=True)
class NarStatusAwareAsOfTarget:
    race_key: RaceKey = field(repr=False)
    horse_number: int = field(repr=False)
    horse_identity: Identity = field(repr=False)
    feature: NarAsOfFeatures
    target_win: int = field(repr=False)
    target_place: int = field(repr=False)
    # Three-finisher rank target, NOT a place-ticket dividend (5-7 runners
    # pay only two). Never used among features or for ROI.
    target_top3: int = field(repr=False)
    # Target status MUST NOT enter feature.
    after_event_status: str = field(repr=False)


@dataclass(frozen=True)
class NarStatusAwareAsOfAudit:
    months: int
    source_flat_races: int
    validated_flat_races: int
    unresolved_flat_races: int
    projected_target_rows: int
    no_target_scratch_or_exclusion_rows: int
    no_target_disqualification_rows: int
    historical_started_rows: int
    historical_ranked_rows: int
    target_rows_with_prior_start: int
    target_rows_without_prior_start: int
    target_rows_with_prior_win: int
    target_rows_with_prior_top3: int
    target_rows_with_numeric_prior_finish: int
    usable_for_training: bool = False
    independently_captured_preoff_roster: bool = False
    official_source_rights_verified: bool = False
    independent_oos_opened: bool = False
    positive_expected_value_demonstrated: bool = False
    source_rows_exported: bool = False


@dataclass(frozen=True)
class NarStatusAwareAsOfBatch:
    audit: NarStatusAwareAsOfAudit
    targets: tuple[NarStatusAwareAsOfTarget, ...] = field(repr=False)


@dataclass(slots=True)
class _State:
    starts: int = 0
    wins: int = 0
    top3: int = 0
    ranked: int = 0
    rank_sum: int = 0
    last_started: date | None = None


def reconstruct_nar_status_aware_prior_day(
    months: Iterable[tuple[str, NarPostEventLabelBatch, Mapping[EntrantKey, Identity]]],
    *,
    allow_incomplete_diagnostic: bool = False,
    allow_explicit_exploratory_sample: bool = False,
) -> NarStatusAwareAsOfBatch:
    """Project as-of-date form from a bounded, chronological month stream.

    Source-specific identities must be paired from the same authorized
    horselist rows, using (horse name, birth YYYYMMDD) not name alone.
    Incomplete historic months normally return NO target rows.
    An explicit opt-in may return an in-memory *biased retrospective*
    sample for exploratory ranking screening ONLY. It does NOT confer
    training-readiness, historical preoff evidence or economic ROI rights.
    """
    if (type(allow_incomplete_diagnostic) is not bool
            or type(allow_explicit_exploratory_sample) is not bool
            or (allow_explicit_exploratory_sample
                and not allow_incomplete_diagnostic)):
        raise UnsafeNarSource("NAR_ASOF_DIAGNOSTIC_MODE_INVALID")
    history: dict[Identity, _State] = {}
    targets: list[NarStatusAwareAsOfTarget] = []
    previous_month = ""
    previous_day: date | None = None
    count_months = source = validated = unresolved = ignored = disputed = 0
    started = ranked = 0
    prior_starts_seen = no_prior_starts = prior_win_seen = 0
    prior_podium_seen = prior_finish_seen = 0

    for month, batch, identities in months:
        if (type(month) is not str or len(month) != 6
                or not month.isascii() or not month.isdecimal()
                or not "201701" <= month <= "202212"
                or month <= previous_month
                or not isinstance(batch, NarPostEventLabelBatch)
                or not isinstance(identities, Mapping)
                or batch.audit.model_training_authorized
                or batch.audit.realized_roi_authorized
                or batch.audit.positive_expected_value_demonstrated):
            raise UnsafeNarSource("NAR_ASOF_SOURCE_MONTH_ORDER_OR_RIGHTS_INVALID")
        count_months += 1
        if count_months > 72:
            raise UnsafeNarSource("NAR_ASOF_TOO_MANY_TRAINING_MONTHS")
        a = batch.audit
        source += a.in_scope_flat_races
        validated += a.validated_flat_races
        unresolved += a.unresolved_flat_races
        if (a.validated_flat_races + a.unresolved_flat_races
                != a.in_scope_flat_races or
                a.labeled_runner_rows > a.observed_roster_rows):
            raise UnsafeNarSource("NAR_ASOF_AGGREGATE_SOURCE_MISMATCH")
        if a.unresolved_flat_races and not allow_incomplete_diagnostic:
            raise UnsafeNarSource("NAR_ASOF_INCOMPLETE_MONTH_FAIL_CLOSED")

        label_map: dict[EntrantKey, NarHistoricalOutcomeLabel] = {}
        grouped: dict[date, list[EntrantKey]] = defaultdict(list)
        for row in batch.labels:
            key = row.race_key, row.horse_number
            if key in label_map or key not in identities:
                raise UnsafeNarSource("NAR_ASOF_LABEL_IDENTITY_COVERAGE_MISMATCH")
            label_map[key] = row
            if row.race_key[1][:6] != month:
                raise UnsafeNarSource("NAR_ASOF_MONTH_VS_RACE_KEY_INVALID")
            try:
                race_day = date.fromisoformat(
                    f"{row.race_key[1][:4]}-{row.race_key[1][4:6]}-{row.race_key[1][6:]}"
                )
            except (TypeError, ValueError):
                raise UnsafeNarSource("NAR_ASOF_RACE_DATE_INVALID") from None
            grouped[race_day].append(key)
        if (len(label_map) != a.observed_roster_rows or
                set(identities) != set(label_map)):
            raise UnsafeNarSource("NAR_ASOF_LABEL_IDENTITY_COVERAGE_MISMATCH")

        for current_day in sorted(grouped):
            if previous_day is not None and current_day <= previous_day:
                raise UnsafeNarSource("NAR_ASOF_CHRONOLOGY_VIOLATION")
            changes: list[tuple[Identity, NarHistoricalOutcomeLabel]] = []
            today: set[Identity] = set()
            for key in sorted(grouped[current_day]):
                label = label_map[key]
                identity = identities[key]
                if (not isinstance(identity, tuple) or len(identity) != 2
                        or not isinstance(identity[0], str)
                        or not 1 <= len(identity[0].strip()) <= 100):
                    raise UnsafeNarSource("NAR_ASOF_HORSE_IDENTITY_UNVERIFIED")
                identity = identity[0].strip(), _birthday(identity[1])
                if identity in today:
                    raise UnsafeNarSource("NAR_ASOF_SAME_HORSE_TWICE_ONE_DAY")
                today.add(identity)
                previous = history.get(identity, _State())
                if previous.last_started is not None and previous.last_started >= current_day:
                    raise UnsafeNarSource("NAR_ASOF_CHRONOLOGY_VIOLATION")
                days_since = (
                    (current_day - previous.last_started).days
                    if previous.last_started else None
                )
                features = NarAsOfFeatures(
                    prior_starts=previous.starts,
                    prior_wins=previous.wins,
                    prior_top3=previous.top3,
                    prior_win_rate=previous.wins / previous.starts
                    if previous.starts else 0.0,
                    prior_top3_rate=previous.top3 / previous.starts
                    if previous.starts else 0.0,
                    # DNFs counted as starts, but excluded from the mean's
                    # numeric denominator. No fake rank 18 is inserted.
                    prior_mean_finish=previous.rank_sum / previous.ranked
                    if previous.ranked else None,
                    days_since_prior_start=days_since,
                )
                if label.win_label is not None:
                    if (type(label.win_label) is not int or
                            type(label.place_label) is not int or
                            label.win_label not in (0, 1) or
                            label.place_label not in (0, 1)):
                        raise UnsafeNarSource("NAR_ASOF_SUPERVISED_LABEL_INVALID")
                    # Aggregate-only diagnostic of *historical feature
                    # availability*, never current-race rank/market data.
                    prior_starts_seen += int(previous.starts > 0)
                    no_prior_starts += int(previous.starts == 0)
                    prior_win_seen += int(previous.wins > 0)
                    prior_podium_seen += int(previous.top3 > 0)
                    prior_finish_seen += int(previous.ranked > 0)
                    targets.append(NarStatusAwareAsOfTarget(
                        race_key=label.race_key, horse_number=label.horse_number,
                        horse_identity=identity, feature=features,
                        target_win=label.win_label,
                        target_place=label.place_label,
                        target_top3=int(
                            label.official_finish_rank is not None
                            and label.official_finish_rank <= 3
                        ),
                        after_event_status=label.status,
                    ))
                    if len(targets) > 1_000_000:
                        raise UnsafeNarSource("NAR_ASOF_TARGET_MEMORY_BOUND")
                elif label.status in {"SCRATCH_NOT_OFFERED", "EXCLUDED_REFUND"}:
                    ignored += 1
                elif label.status == "DISQUALIFIED_REVIEW":
                    disputed += 1
                else:
                    raise UnsafeNarSource("NAR_ASOF_MISSING_TARGET_STATUS_INVALID")
                changes.append((identity, label))
            # IMPORTANT: do not update a single runner before creating ALL
            # same-day target features, across all racecards/venues.
            for identity, label in changes:
                if label.prior_start_increment:
                    state = history.setdefault(identity, _State())
                    state.starts += 1
                    state.wins += int(label.win_label == 1)
                    # Top-3 form is a FINISH metric, not a place
                    # dividend: 5-7 starters pay only top 2 for place.
                    state.top3 += int(
                        label.official_finish_rank is not None
                        and label.official_finish_rank <= 3
                    )
                    if label.prior_numeric_rank_observed:
                        if type(label.official_finish_rank) is not int:
                            raise UnsafeNarSource("NAR_ASOF_NUMERIC_HISTORY_INVALID")
                        state.ranked += 1
                        state.rank_sum += label.official_finish_rank
                    state.last_started = current_day
                    started += 1
                    ranked += int(label.prior_numeric_rank_observed)
            previous_day = current_day
        previous_month = month

    if not count_months:
        raise UnsafeNarSource("NAR_ASOF_NO_MONTHS")
    if prior_starts_seen + no_prior_starts != len(targets):
        raise UnsafeNarSource("NAR_ASOF_HISTORICAL_FEATURE_COVERAGE_INVALID")
    return NarStatusAwareAsOfBatch(
        audit=NarStatusAwareAsOfAudit(
            months=count_months, source_flat_races=source,
            validated_flat_races=validated, unresolved_flat_races=unresolved,
            projected_target_rows=len(targets),
            no_target_scratch_or_exclusion_rows=ignored,
            no_target_disqualification_rows=disputed,
            historical_started_rows=started, historical_ranked_rows=ranked,
            target_rows_with_prior_start=prior_starts_seen,
            target_rows_without_prior_start=no_prior_starts,
            target_rows_with_prior_win=prior_win_seen,
            target_rows_with_prior_top3=prior_podium_seen,
            target_rows_with_numeric_prior_finish=prior_finish_seen,
        ),
        targets=tuple(targets) if (
            unresolved == 0 or allow_explicit_exploratory_sample
        ) else (),
    )
