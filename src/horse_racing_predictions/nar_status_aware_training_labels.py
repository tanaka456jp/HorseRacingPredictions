"""Research-only NAR supervised-outcome labels with official status semantics.

Consumes already privately normalized *post-event* NAR official data.
No race is removed from source denominators and no status is guessed from
a blank finish rank. This is NOT a pre-off feature builder, executable
training authorization, purchased-ticket ledger, or expected-value proof.

Official NAR rules:
https://www.keiba.go.jp/beginner/step2.html
https://www.keiba.go.jp/beginner/step6.html
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .nar_official_exception_audit import NarOfficialExceptionDetail
from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import RaceKey


@dataclass(frozen=True)
class NarHistoricalOutcomeLabel:
    race_key: RaceKey = field(repr=False)
    horse_number: int = field(repr=False)
    status: str
    started_race: bool
    betting_option_offered: bool  # opportunity, never evidence of purchase
    official_finish_rank: int | None
    win_label: int | None
    place_label: int | None
    # Historical form: a runner who did not finish has a start without a
    # numeric finish rank. Neither a scratch nor a late exclusion has a start.
    prior_start_increment: int
    prior_numeric_rank_observed: bool
    # Backfilled final status is never a prospective race-day predictor.
    usable_as_preoff_feature: bool = False


@dataclass(frozen=True)
class NarPostEventLabelAudit:
    source_races: int
    in_scope_flat_races: int
    validated_flat_races: int
    unresolved_flat_races: int
    observed_roster_rows: int
    labeled_runner_rows: int
    excluded_scratch_rows: int
    excluded_refunded_rows: int
    unknown_disqualification_rows: int
    official_started_rows: int
    official_finished_rows: int
    status: str = "NAR_POST_EVENT_LABELS_ONLY_NO_TRAINING_APPROVAL"
    pre_event_availability_proven: bool = False
    source_rights_independently_verified: bool = False
    model_training_authorized: bool = False
    realized_roi_authorized: bool = False
    positive_expected_value_demonstrated: bool = False
    source_bytes_exported: bool = False


@dataclass(frozen=True)
class NarPostEventLabelBatch:
    audit: NarPostEventLabelAudit
    labels: tuple[NarHistoricalOutcomeLabel, ...] = field(repr=False)


def derive_nar_status_aware_outcome_labels(
    report: NarOfficialExceptionDetail,
) -> NarPostEventLabelBatch:
    """Retain DNF as a nonwinning START; never label scratches as losses.

    Incomplete/contradictory races stay in the race denominator, but have
    no labels. This function does not silently choose an economically
    favorable sample or assert that their pre-event rosters were known.
    """
    if (not isinstance(report, NarOfficialExceptionDetail)
            or report.audit.training_authorized
            or report.audit.economic_roi_authorized
            or report.audit.positive_ev_demonstrated
            or report.audit.source_bytes_exported
            or report.audit.status_validated_flat_races != len(report.validated_races)
            or report.audit.status_validated_flat_races
               + report.audit.unresolved_flat_races
               != report.audit.in_scope_flat_races
            or report.audit.predeclared_banei_races
               + report.audit.in_scope_flat_races != report.audit.source_races):
        raise UnsafeNarSource("NAR_STATUS_LABEL_SOURCE_AUDIT_INVALID")

    out = []
    scratch = excluded = disputed = labeled = started = finished = rows = 0
    seen = set()
    for race in report.validated_races:
        if race.race_key in seen or race.economic_roi_authorized or race.pre_event_availability_proven:
            raise UnsafeNarSource("NAR_STATUS_LABEL_UNEXPECTED_RACE_OR_RIGHTS")
        seen.add(race.race_key)
        statuses = dict(race.status_by_number)
        ranks = dict(race.rank_by_number)
        wins = dict(race.win_yen_by_number)
        places = dict(race.place_yen_by_number)
        if (not 2 <= len(statuses) <= 18 or
                len(statuses) != len(race.status_by_number) or
                set(statuses) != set(ranks) or
                set(statuses) != set(wins) or
                set(statuses) != set(places)):
            raise UnsafeNarSource("NAR_STATUS_LABEL_ROSTER_MISMATCH")
        before_row_count = rows
        for horse in sorted(statuses):
            status, rank = statuses[horse], ranks[horse]
            win, place = wins[horse], places[horse]
            if status == "FINISHED":
                if (type(rank) is not int or not 1 <= rank <= 18
                        or type(win) is not int or win < 0
                        or type(place) is not int or place < 0):
                    raise UnsafeNarSource("NAR_STATUS_LABEL_FINISH_INVALID")
                wl, pl = int(win > 0), int(place > 0)
                started_flag = True
                offered_flag = True
                numeric_rank = True
                finished += 1
            elif status == "DNF_NO_REFUND":
                if rank is not None or win != 0 or place != 0:
                    raise UnsafeNarSource("NAR_STATUS_LABEL_DNF_INVALID")
                wl = pl = 0
                started_flag = sold_flag = True
                numeric_rank = False
            elif status == "SCRATCH_NOT_OFFERED":
                if rank is not None or win is not None or place is not None:
                    raise UnsafeNarSource("NAR_STATUS_LABEL_SCRATCH_INVALID")
                wl = pl = None
                started_flag = sold_flag = numeric_rank = False
                scratch += 1
            elif status == "EXCLUDED_REFUND":
                if rank is not None or win != 100 or place != 100:
                    raise UnsafeNarSource("NAR_STATUS_LABEL_EXCLUSION_INVALID")
                wl = pl = None
                started_flag = numeric_rank = False
                offered_flag = True  # ticket MAY have been purchased; not proof
                excluded += 1
            elif status == "DISQUALIFIED_REVIEW":
                if rank is not None or win is not None or place is not None:
                    raise UnsafeNarSource("NAR_STATUS_LABEL_DQ_INVALID")
                wl = pl = None
                started_flag = sold_flag = True
                numeric_rank = False
                disputed += 1
            else:
                raise UnsafeNarSource("NAR_STATUS_LABEL_UNKNOWN_OFFICIAL_STATUS")
            started += int(started_flag)
            labeled += int(wl is not None)
            rows += 1
            out.append(NarHistoricalOutcomeLabel(
                race_key=race.race_key, horse_number=horse,
                status=status, started_race=started_flag,
                betting_option_offered=sold_flag,
                official_finish_rank=rank, win_label=wl,
                place_label=pl, prior_start_increment=int(started_flag),
                prior_numeric_rank_observed=numeric_rank,
            ))
        if rows - before_row_count != len(statuses):
            raise UnsafeNarSource("NAR_STATUS_LABEL_RACE_COVERAGE_MISMATCH")
    if rows != labeled + scratch + excluded + disputed:
        raise UnsafeNarSource("NAR_STATUS_LABEL_ACCOUNTING_MISMATCH")
    return NarPostEventLabelBatch(
        audit=NarPostEventLabelAudit(
            source_races=report.audit.source_races,
            in_scope_flat_races=report.audit.in_scope_flat_races,
            validated_flat_races=report.audit.status_validated_flat_races,
            unresolved_flat_races=report.audit.unresolved_flat_races,
            observed_roster_rows=rows,
            labeled_runner_rows=labeled,
            excluded_scratch_rows=scratch,
            excluded_refunded_rows=excluded,
            unknown_disqualification_rows=disputed,
            official_started_rows=started,
            official_finished_rows=finished,
        ),
        labels=tuple(out),
    )
