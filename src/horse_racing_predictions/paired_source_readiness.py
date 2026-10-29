"""Fail-closed matching of two separately sourced private research CSVs.

Exactly the same race/runner identities and dates must be backed by history
and official-settlement candidates before any payout-based research starts.
Local operator only: the input permissions and Friday freeze are NOT proven
by this structural check. No source rows or identifiers are returned.
No web, provider access, model fitting, note posting or archive workflow.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

from .alternative_source_intake import inspect_alternative_csv
from .pre2025_training_csv_audit import (
    REQUIRED_ALIASES, UnsafeTrainingSource, _date_cell,
)

_MAX_RUNNERS = 18


@dataclass(frozen=True)
class PairedSourceReadiness:
    status: str
    history_rows: int
    payout_rows: int
    matched_races: int
    matched_runners: int
    eligible_first_year: int
    eligible_last_year: int
    full_roster_and_payout_coverage: bool
    verified_friday_availability: bool = False
    verified_official_payout_rights: bool = False
    authorized_for_model_training: bool = False
    authorized_for_real_roi: bool = False
    publication_authorized: bool = False
    protected_holdout_opened: bool = False


def _rows(path: Path, kind: str) -> Iterator[tuple[str, str, date, int, int]]:
    """Yield locally sorted rows, strict duplicate/sequence checks."""
    names = ("race_id", "race_date", "horse_name")
    if kind == "history":
        names += ("finish_position",)
    else:
        names += ("win_return_per_100_yen", "place_return_per_100_yen")
    encodings = ("utf-8-sig", "cp932", "euc_jp")
    selected = None
    # Detect whole-file encoding before the comparison, using existing
    # pre-audited private files without persisting any source content.
    for enc in encodings:
        try:
            with path.open("r", encoding=enc, errors="strict", newline="") as f:
                for _ in f:
                    pass
            selected = enc
            break
        except UnicodeDecodeError:
            continue
    if selected is None:
        raise UnsafeTrainingSource("PAIR_SOURCE_ENCODING_INVALID")
    with path.open("r", encoding=selected, errors="strict", newline="") as f:
        try:
            reader = csv.reader(f, strict=True)
            headers = [h.strip().lstrip("\ufeff") for h in next(reader)]
            idx = []
            for name in names:
                aliases = REQUIRED_ALIASES.get(name, (name,))
                matched = [n for n, h in enumerate(headers) if h in aliases]
                if len(matched) != 1:
                    raise UnsafeTrainingSource("PAIR_COLUMN_MISSING_OR_AMBIGUOUS")
                idx.append(matched[0])
            last_key: tuple[str, str] | None = None
            for row in reader:
                if len(row) != len(headers):
                    raise UnsafeTrainingSource("PAIR_ROW_MALFORMED")
                rid, raw_day, horse = (row[i].strip() for i in idx[:3])
                if not rid or not horse:
                    raise UnsafeTrainingSource("PAIR_IDENTITY_MISSING")
                key = (rid, horse)
                if last_key is not None and key <= last_key:
                    raise UnsafeTrainingSource("PAIR_INPUT_MUST_SORT_BY_RACE_AND_HORSE")
                last_key = key
                day = _date_cell(raw_day)
                if kind == "history":
                    raw_finish = row[idx[3]].strip()
                    if not raw_finish.isdecimal():
                        raise UnsafeTrainingSource("PAIR_FINISH_INVALID")
                    finish = int(raw_finish)
                    yield rid, horse, day, finish, -1
                else:
                    raw_win, raw_place = (
                        row[idx[3]].strip(), row[idx[4]].strip(),
                    )
                    if (not raw_win.isdecimal() or not raw_place.isdecimal()
                            or len(raw_win) > 9 or len(raw_place) > 9):
                        raise UnsafeTrainingSource("PAIR_PAYOUT_INVALID")
                    yield rid, horse, day, int(raw_win), int(raw_place)
        except (csv.Error, StopIteration):
            raise UnsafeTrainingSource("PAIR_CSV_MALFORMED") from None


def inspect_paired_sources(
    history_csv: Path, history_manifest: Path,
    payout_csv: Path, payout_manifest: Path, *,
    today: date | None = None,
) -> PairedSourceReadiness:
    """Structural full-coverage gate for pre-2025 research candidates only.

    Evidence of data provenance, time-of-availability, actual official payouts
    and any source rights are separate operator-reviewed decisions.
    """
    if history_csv == payout_csv or history_manifest == payout_manifest:
        raise UnsafeTrainingSource("PAIR_SOURCES_MUST_BE_INDEPENDENT")
    history = inspect_alternative_csv(
        history_csv, history_manifest, kind="history", today=today,
    )
    payout = inspect_alternative_csv(
        payout_csv, payout_manifest, kind="settlement", today=today,
    )
    hist_iter = _rows(history_csv, "history")
    payout_iter = _rows(payout_csv, "settlement")
    total = races = 0
    active_race = None
    active_day: date | None = None
    count = 0
    finishes: set[int] = set()
    place_rows: list[tuple[int, int]] = []
    year_min = 9999
    year_max = 0

    def validate_race() -> None:
        if active_race is None:
            return
        if (not 5 <= count <= _MAX_RUNNERS
                or finishes != set(range(1, count + 1))):
            raise UnsafeTrainingSource("PAIR_COMPLETE_STANDARD_RACE_REQUIRED")
        place_cutoff = 2 if count <= 7 else 3
        if any(
            (amount > 0) != (finish <= place_cutoff)
            or (amount > 0 and amount < 100)
            for finish, amount in place_rows
        ):
            raise UnsafeTrainingSource("PAIR_PLACE_PAYOUT_CONTRADICTION")

    from itertools import zip_longest
    sentinel = object()
    for h, p in zip_longest(hist_iter, payout_iter, fillvalue=sentinel):
        if h is sentinel or p is sentinel:
            raise UnsafeTrainingSource("PAIR_MISSING_RESULT_OR_PAYOUT_ROW")
        hrid, hhorse, hday, rank, _ = h
        prid, phorse, pday, win, place = p
        if (hrid, hhorse, hday) != (prid, phorse, pday):
            raise UnsafeTrainingSource("PAIR_IDENTITY_DATE_OR_COVERAGE_MISMATCH")
        if hrid != active_race:
            validate_race()
            active_race = hrid
            active_day = hday
            count = 0
            finishes = set()
            place_rows = []
            races += 1
        if hday != active_day:
            raise UnsafeTrainingSource("PAIR_RACE_DATE_CONFLICT")
        count += 1
        finishes.add(rank)
        place_rows.append((rank, place))
        # Normal, non-dead-heat races only. Do not impute money from odds.
        # Eligibility excludes races with <5 entrants; the caller must keep
        # a rejection ledger rather than silently dropping them.
        if not 1 <= rank <= _MAX_RUNNERS:
            raise UnsafeTrainingSource("PAIR_FINISH_INVALID")
        if (win != 0) != (rank == 1) or (win > 0 and win < 100):
            raise UnsafeTrainingSource("PAIR_WIN_PAYOUT_CONTRADICTION")
        total += 1
        year_min = min(year_min, hday.year)
        year_max = max(year_max, hday.year)
        if total > 3_000_000:
            raise UnsafeTrainingSource("PAIR_TOO_MANY_ROWS")
    validate_race()
    if total != history.total_rows or total != payout.total_rows or races == 0:
        raise UnsafeTrainingSource("PAIR_ROW_COUNT_MISMATCH")
    return PairedSourceReadiness(
        status="STRUCTURAL_MATCH_ONLY_RIGHTS_AND_FRIDAY_EVIDENCE_PENDING",
        history_rows=history.total_rows,
        payout_rows=payout.total_rows,
        matched_races=races,
        matched_runners=total,
        eligible_first_year=year_min,
        eligible_last_year=year_max,
        full_roster_and_payout_coverage=True,
    )
