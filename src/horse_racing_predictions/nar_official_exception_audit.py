"""Read-only, private, status-aware NAR result audit for old monthly CSVs.

Official NAR 36-column horselist stores exceptional finish markers in the
'着差' (index 33) cell when '着順' (index 31) is blank. That field is NOT
an independent pre-race snapshot. It is after-result evidence only.

This module does not edit the strict historical training/economics pipeline:
a retrospective status interpretation cannot prove which horses were
purchasable when an independently frozen prediction was made. In particular
do not treat SCRATCH (not offered), EXCLUDED (refund), DNF (losing wager)
and DISQUALIFIED (settlement to verify) as interchangeable.
No network, files, ZIP, uploads or log output.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
from typing import Mapping

from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import (
    _EXPECTED_WIDTH, _parse, _numeric, _payout_pairs,
    _competition_rank_sequence, RaceKey,
)

# Source: https://www.keiba.go.jp/beginner/step2.html
# Exhaustive allowlist: no guessing based on time, odds, popularity or rank gap.
_MARKERS = {
    "取消": "SCRATCH_NOT_OFFERED",
    "出走取消": "SCRATCH_NOT_OFFERED",
    "除外": "EXCLUDED_REFUND",
    "競走除外": "EXCLUDED_REFUND",
    "中止": "DNF_NO_REFUND",
    "競走中止": "DNF_NO_REFUND",
    "失格": "DISQUALIFIED_REVIEW",
}
_RETURN_UNKNOWN = None
# These labels are *possible* indicators, not proven NAR return rules.
# Source marker text must not be surfaced in public Actions logs.
_KNOWN_UNRESOLVED_SHORT_LABELS = {
    "発除": "POSSIBLE_PRESTART_EXCLUSION_ABBREVIATION",
    "競除": "POSSIBLE_PRESTART_EXCLUSION_ABBREVIATION",
    "発走除外": "POSSIBLE_PRESTART_EXCLUSION_ABBREVIATION",
    "出除": "POSSIBLE_PRESTART_EXCLUSION_ABBREVIATION",
    "取消し": "POSSIBLE_SCRATCH_VARIANT",
    "取": "POSSIBLE_SCRATCH_VARIANT",
    "中": "POSSIBLE_DNF_VARIANT",
    "落馬": "POSSIBLE_DNF_VARIANT",
    "再騎": "OTHER_RESULT_EXCEPTION_VARIANT",
    "降着": "OTHER_RESULT_EXCEPTION_VARIANT",
    "タイムオーバー": "OTHER_RESULT_EXCEPTION_VARIANT",
}


def _unknown_status_profile(raw: str) -> str:
    """Public-static structural class, never arbitrary source text."""
    value = raw.strip()
    if value in _KNOWN_UNRESOLVED_SHORT_LABELS:
        return _KNOWN_UNRESOLVED_SHORT_LABELS[value]
    if any(k in value for k in ("除外", "発除", "競除")):
        return "POSSIBLE_PRESTART_EXCLUSION_ABBREVIATION"
    if any(k in value for k in ("取消",)):
        return "POSSIBLE_SCRATCH_VARIANT"
    if any(k in value for k in ("中止", "落馬")):
        return "POSSIBLE_DNF_VARIANT"
    if any(k in value for k in ("失格", "降着")):
        return "OTHER_RESULT_EXCEPTION_VARIANT"
    if re.fullmatch(r"[0-9０-９]+(?:[.,．][0-9０-９]+)?", value):
        return "UNEXPECTED_NUMERIC_MARGIN"
    if value and all(ch in "-—―－ー*＊※・□△？?!" for ch in value):
        return "UNEXPECTED_PUNCTUATION_PLACEHOLDER"
    length = len(value)
    if length <= 2:
        return "UNRECOGNIZED_TEXT_1_OR_2_CHARS"
    if length <= 5:
        return "UNRECOGNIZED_TEXT_3_TO_5_CHARS"
    return "UNRECOGNIZED_TEXT_6_PLUS_CHARS"

# Known NAR result words that are NOT horse-level finished/loser statuses.
# They require separate race-level refund provenance before interpretation.
_CANCEL_OR_NON_ESTABLISHED_MARKERS = frozenset({
    "取止", "競走取止", "競走取り止め", "不成", "競走不成立",
})


@dataclass(frozen=True)
class NarStatusAwareRace:
    race_key: RaceKey = field(repr=False)
    status_by_number: tuple[tuple[int, str], ...] = field(repr=False)
    rank_by_number: tuple[tuple[int, int | None], ...] = field(repr=False)
    # Hypothetical 100-yen ticket returns, *not* proof of ticket purchase:
    # None means not offered / unsettled, not a refunded or losing ticket.
    win_yen_by_number: tuple[tuple[int, int | None], ...] = field(repr=False)
    place_yen_by_number: tuple[tuple[int, int | None], ...] = field(repr=False)
    offered_field_size: int
    actual_starting_horses: int
    economic_roi_authorized: bool = False
    pre_event_availability_proven: bool = False


@dataclass(frozen=True)
class NarOfficialExceptionAudit:
    status: str
    source_races: int
    predeclared_banei_races: int
    in_scope_flat_races: int
    status_validated_flat_races: int
    unresolved_flat_races: int
    status_horse_counts: tuple[tuple[str, int], ...]
    unresolved_reason_counts: tuple[tuple[str, int], ...]
    complete_flat_outcome_interpretation: bool
    # Exclusively aggregate categories for the original blank/unknown-status
    # error. No private margin text, race key or horse identity is exposed.
    ambiguous_finish_pattern_counts: tuple[tuple[str, int], ...] = ()
    # Unknown margin labels are counted by fixed token families only,
    # without printing actual licensed source strings.
    unrecognized_marker_profile_counts: tuple[tuple[str, int], ...] = ()
    unknown_marker_rank_evidence: tuple[tuple[str, int], ...] = ()
    unknown_marker_win_payout_evidence: tuple[tuple[str, int], ...] = ()
    unknown_marker_distinct_text_values_in_month: int = 0
    unknown_marker_largest_single_value_frequency_in_month: int = 0
    training_authorized: bool = False
    economic_roi_authorized: bool = False
    positive_ev_demonstrated: bool = False
    source_bytes_exported: bool = False


@dataclass(frozen=True)
class NarOfficialExceptionDetail:
    audit: NarOfficialExceptionAudit
    validated_races: tuple[NarStatusAwareRace, ...] = field(repr=False)


def _status_and_rank(row: list[str]) -> tuple[str, int | None]:
    raw_rank = row[31].strip()
    margin = row[33].strip()
    if raw_rank:
        if margin in _MARKERS:
            raise UnsafeNarSource("NAR_CONFLICTING_RANK_AND_EXCEPTION")
        return "FINISHED", _numeric(
            raw_rank, "NAR_FINISH_RANK_INVALID", minimum=1, maximum=18,
        )
    status = _MARKERS.get(margin)
    if status is None:
        raise UnsafeNarSource("NAR_BLANK_WITHOUT_OFFICIAL_STATUS")
    return status, None


def _validated_race(
    key: RaceKey, racelist: list[str],
    horse_rows: list[list[str]], payout_rows: list[list[str]],
) -> NarStatusAwareRace:
    declared = _numeric(
        racelist[26], "NAR_DECLARED_STARTERS_INVALID", minimum=5, maximum=18,
    )
    if len(horse_rows) != declared:
        raise UnsafeNarSource("NAR_RACE_STARTER_COUNT_MISMATCH")
    by_number: dict[int, tuple[str, int | None]] = {}
    for row in horse_rows:
        number = _numeric(
            row[5], "NAR_STARTER_NUMBER_INVALID", minimum=1, maximum=18,
        )
        if number in by_number:
            raise UnsafeNarSource("NAR_DUPLICATE_STARTER")
        if not row[6].strip():
            raise UnsafeNarSource("NAR_STARTER_NAME_MISSING")
        by_number[number] = _status_and_rank(row)
    numeric_ranks = [rank for status, rank in by_number.values() if rank is not None]
    if (_competition_rank_sequence(numeric_ranks)
            not in {"COMPLETE", "DEAD_HEAT"}):
        raise UnsafeNarSource("NAR_STATUS_AWARE_RANKS_INCOMPLETE")
    purchased_field = declared - sum(
        status == "SCRATCH_NOT_OFFERED" for status, _ in by_number.values()
    )
    starters = sum(
        status in {"FINISHED", "DNF_NO_REFUND", "DISQUALIFIED_REVIEW"}
        for status, _ in by_number.values()
    )
    if not 2 <= starters <= 18 or purchased_field < starters:
        raise UnsafeNarSource("NAR_STATUS_AWARE_FIELD_SIZE_INVALID")

    win: dict[int, int] = {}
    place: dict[int, int] = {}
    payout_seen: list[list[str]] = []
    for row in payout_rows:
        if row in payout_seen:
            raise UnsafeNarSource("NAR_IDENTICAL_DUPLICATE_PAYOUT_ROW")
        payout_seen.append(row)
        if len(payout_seen) > 18:
            raise UnsafeNarSource("NAR_EXCESSIVE_OFFICIAL_PAYOUT_ROWS")
        for pairs, dest in (
            (((4, 5),), win),
            (((7, 8), (10, 11), (13, 14)), place),
        ):
            for horse, amount in _payout_pairs(row, pairs).items():
                if horse in dest and dest[horse] != amount:
                    raise UnsafeNarSource("NAR_OFFICIAL_MULTIROW_PAYOUT_CONFLICT")
                dest[horse] = amount

    winners = {
        number for number, (_, rank) in by_number.items() if rank == 1
    }
    # Sale-time field decides the wager type, not a post-event count
    # reduced by competition exclusions or failures to finish.
    cutoff = 3 if purchased_field >= 8 else (2 if purchased_field >= 5 else 0)
    placers = {
        number for number, (_, rank) in by_number.items()
        if rank is not None and rank <= cutoff
    }
    if set(win) != winners:
        # Disclose only a fixed mismatch *direction*. No horse number,
        # race ID or source text is emitted into the aggregate report.
        missing = bool(winners - set(win))
        unexpected = bool(set(win) - winners)
        if missing and unexpected:
            # A paid ticket on a runner whose archived *final* status is
            # disqualified may reflect later adjudication. We can identify
            # that structural conflict, but NOT infer its chronology.
            unexpected_paid = set(win) - winners
            if any(
                by_number[n][0] == "DISQUALIFIED_REVIEW"
                for n in unexpected_paid if n in by_number
            ):
                code = "NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS"
            else:
                code = "NAR_WIN_PAYOUT_BOTH_MISSING_AND_UNEXPECTED"
        elif missing:
            code = "NAR_WIN_PAYOUT_MISSING_RANK_ONE"
        else:
            code = "NAR_WIN_PAYOUT_TO_NON_RANK_ONE"
        raise UnsafeNarSource(code)
    if set(place) != placers:
        raise UnsafeNarSource("NAR_STATUS_AWARE_PLACE_PAYOUT_MISMATCH")

    def theoretical_return(status: str, n: int, actual: Mapping[int, int]) -> int | None:
        if status in {"SCRATCH_NOT_OFFERED", "DISQUALIFIED_REVIEW"}:
            return _RETURN_UNKNOWN
        if status == "EXCLUDED_REFUND":
            return 100
        if status == "DNF_NO_REFUND":
            return 0
        return actual.get(n, 0)

    sorted_numbers = sorted(by_number)
    return NarStatusAwareRace(
        race_key=key,
        status_by_number=tuple((n, by_number[n][0]) for n in sorted_numbers),
        rank_by_number=tuple((n, by_number[n][1]) for n in sorted_numbers),
        win_yen_by_number=tuple(
            (n, theoretical_return(by_number[n][0], n, win))
            for n in sorted_numbers
        ),
        place_yen_by_number=tuple(
            (n, theoretical_return(by_number[n][0], n, place))
            for n in sorted_numbers
        ),
        offered_field_size=purchased_field,
        actual_starting_horses=starters,
    )


def audit_nar_official_exceptions(
    csv_texts: Mapping[str, str], *, month: str,
) -> NarOfficialExceptionDetail:
    if not isinstance(csv_texts, Mapping) or set(csv_texts) != set(_EXPECTED_WIDTH):
        raise UnsafeNarSource("NAR_EXPLICIT_THREE_CSVS_AND_MONTH_REQUIRED")
    parsed = {kind: _parse(csv_texts[kind], kind, month)
              for kind in _EXPECTED_WIDTH}
    groups = {}
    for kind, entries in parsed.items():
        grouped = defaultdict(list)
        for key, row in entries:
            grouped[key].append(row)
        groups[kind] = grouped

    keys = sorted(set().union(*(set(k) for k in groups.values())))
    if not keys:
        raise UnsafeNarSource("NAR_MONTH_HAS_NO_RACES")
    accepted = []
    reasons: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    ambiguous_finish_patterns: Counter[str] = Counter()
    unrecognized_profiles: Counter[str] = Counter()
    unrecognized_raw_frequency: Counter[str] = Counter()
    unknown_rank_shape: Counter[str] = Counter()
    unknown_win_payout_shape: Counter[str] = Counter()
    banei = flat = 0
    for key in keys:
        if "帯広" in key[0]:
            banei += 1
            continue
        flat += 1
        if (len(groups["racelist"][key]) != 1
                or not groups["horselist"][key]
                or not groups["payback"][key]):
            reasons["NAR_STATUS_AWARE_COVERAGE_MISMATCH"] += 1
            continue
        try:
            race = _validated_race(
                key, groups["racelist"][key][0],
                groups["horselist"][key], groups["payback"][key],
            )
        except UnsafeNarSource as exc:
            # All messages are fixed identifiers; never copy a CSV cell.
            reason = str(exc)
            reasons[reason] += 1
            if reason == "NAR_BLANK_WITHOUT_OFFICIAL_STATUS":
                unknown = [
                    row for row in groups["horselist"][key]
                    if (not row[31].strip()
                        and row[33].strip() not in _MARKERS)
                ]
                if not unknown:
                    raise UnsafeNarSource(
                        "NAR_AMBIGUOUS_STATUS_TRIAGE_INTERNAL_CONFLICT"
                    )
                raw_markers = [row[33].strip() for row in unknown]
                if any(x in _CANCEL_OR_NON_ESTABLISHED_MARKERS
                       for x in raw_markers):
                    shape = "KNOWN_RACE_CANCEL_OR_NON_ESTABLISHED_MARKER"
                elif any(x for x in raw_markers):
                    # Do NOT echo the arbitrary source label.
                    shape = "UNRECOGNIZED_NONEMPTY_STATUS_MARKER"
                    for marker in raw_markers:
                        if marker and marker not in _CANCEL_OR_NON_ESTABLISHED_MARKERS:
                            unrecognized_profiles[_unknown_status_profile(marker)] += 1
                            # Kept only within this one in-memory private
                            # monthly function. Raw text never returned.
                            unrecognized_raw_frequency[marker] += 1
                    if any(row[31].strip() for row in groups["horselist"][key]):
                        unknown_rank_shape["SOME_NUMERIC_FINAL_RANK"] += 1
                    else:
                        unknown_rank_shape["NO_NUMERIC_FINAL_RANK"] += 1
                    # Inspect only presence of the official single-win
                    # payback fields, not the private payout numbers.
                    if any(row[4].strip() and row[5].strip()
                           for row in groups["payback"][key]):
                        unknown_win_payout_shape["WIN_PAYBACK_FIELDS_PRESENT"] += 1
                    else:
                        unknown_win_payout_shape["WIN_PAYBACK_FIELDS_ABSENT"] += 1
                elif len(unknown) == 1:
                    shape = "BOTH_FIELDS_BLANK_ONE_HORSE"
                elif len(unknown) <= 3:
                    shape = "BOTH_FIELDS_BLANK_TWO_OR_THREE_HORSES"
                else:
                    shape = "BOTH_FIELDS_BLANK_FOUR_OR_MORE_HORSES"
                ambiguous_finish_patterns[shape] += 1
            continue
        accepted.append(race)
        status_counts.update(s for _, s in race.status_by_number)
    unresolved = flat - len(accepted)
    assert unresolved == sum(reasons.values())
    assert len(keys) == banei + flat
    return NarOfficialExceptionDetail(
        audit=NarOfficialExceptionAudit(
            status=(
                "NAR_OFFICIAL_STATUS_INTERPRETED_NO_PREOFF_PROOF"
                if not unresolved else "NAR_OFFICIAL_STATUS_INTERPRETATION_HOLD"
            ),
            source_races=len(keys), predeclared_banei_races=banei,
            in_scope_flat_races=flat,
            status_validated_flat_races=len(accepted),
            unresolved_flat_races=unresolved,
            status_horse_counts=tuple(sorted(status_counts.items())),
            unresolved_reason_counts=tuple(sorted(reasons.items())),
            complete_flat_outcome_interpretation=not unresolved,
            ambiguous_finish_pattern_counts=tuple(sorted(
                ambiguous_finish_patterns.items()
            )),
            unrecognized_marker_profile_counts=tuple(sorted(
                unrecognized_profiles.items()
            )),
            unknown_marker_rank_evidence=tuple(sorted(
                unknown_rank_shape.items()
            )),
            unknown_marker_win_payout_evidence=tuple(sorted(
                unknown_win_payout_shape.items()
            )),
            unknown_marker_distinct_text_values_in_month=(
                len(unrecognized_raw_frequency)
            ),
            unknown_marker_largest_single_value_frequency_in_month=(
                max(unrecognized_raw_frequency.values(), default=0)
            ),
        ),
        validated_races=tuple(accepted),
    )
