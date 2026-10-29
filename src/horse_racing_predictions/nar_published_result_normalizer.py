"""Pure, offline normalization of *already authorized* NAR race-result CSV text.

NAR manual (2026-05-21): https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
racelist: 68 fields, horselist: 36, payback: 54. Payback is
ONE ROW PER RACE, not one row per starter; a tie may create extra rows.
This module does not read a ZIP, touch a private archive, download data,
create a pre-race snapshot, train models, export licensed data or publish.
The caller must independently establish source rights before passing text.

Ordinary completed flat races only: reject ties, scratches, missing/ambiguous
returns, and nonstandard place outcomes. No silent denominator selection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
import csv
from typing import Mapping

from .nar_official_zip_probe import UnsafeNarSource

_EXPECTED_WIDTH = {"racelist": 68, "horselist": 36, "payback": 54}
_HEADER_PREFIX = ("競馬場", "競走年月日", "レース番号")
_MAX_INPUT_CHARS = 16_000_000
_MAX_ROWS = 250_000
RaceKey = tuple[str, str, int]


@dataclass(frozen=True)
class NarCompleteRace:
    """Private in-memory *after-result* settlement, never model inputs."""
    race_key: RaceKey = field(repr=False)
    finish_by_number: tuple[tuple[int, int], ...] = field(repr=False)
    win_return_by_number: tuple[tuple[int, int], ...] = field(repr=False)
    place_return_by_number: tuple[tuple[int, int], ...] = field(repr=False)


@dataclass(frozen=True)
class NarHistoricalAudit:
    status: str
    checked_races: int
    checked_starters: int
    min_year: int
    max_year: int
    final_results_only: bool = True
    pre_event_snapshot_verified: bool = False
    authorized_for_model_training: bool = False
    actual_source_rights_independently_verified: bool = False
    positive_ev_demonstrated: bool = False
    publication_authorized: bool = False


@dataclass(frozen=True)
class NarInMemoryResult:
    audit: NarHistoricalAudit
    races: tuple[NarCompleteRace, ...] = field(repr=False)


def _numeric(value: str, error: str, *, minimum: int = 0,
             maximum: int = 999_999_999) -> int:
    value = value.strip()
    if not value.isascii() or not value.isdecimal() or len(value) > 9:
        raise UnsafeNarSource(error)
    result = int(value)
    if not minimum <= result <= maximum:
        raise UnsafeNarSource(error)
    return result


def _optional_number(value: str, error: str, *,
                     maximum: int = 999_999_999) -> int | None:
    if value.strip() == "":
        return None
    return _numeric(value, error, maximum=maximum)


def _race_key(row: list[str], month: str) -> RaceKey:
    track = row[0].strip()
    raw_date = row[1].strip()
    if not track or len(track) > 40 or not raw_date.isascii():
        raise UnsafeNarSource("NAR_RACE_KEY_INVALID")
    try:
        day = datetime.strptime(raw_date, "%Y%m%d").date()
    except ValueError:
        raise UnsafeNarSource("NAR_DATE_INVALID") from None
    if day.strftime("%Y%m%d") != raw_date or day.strftime("%Y%m") != month:
        raise UnsafeNarSource("NAR_DATE_OUTSIDE_ARCHIVE_MONTH")
    if not 1998 <= day.year <= 2024:
        raise UnsafeNarSource("NAR_PROTECTED_OR_INVALID_DATE")
    number = _numeric(row[2], "NAR_RACE_NUMBER_INVALID", minimum=1, maximum=20)
    return track, raw_date, number


def _parse(text: str, kind: str, month: str) -> list[tuple[RaceKey, list[str]]]:
    if (type(text) is not str or not text or len(text) > _MAX_INPUT_CHARS
            or "\x00" in text):
        raise UnsafeNarSource("NAR_CSV_TEXT_INVALID")
    stream = StringIO(text.lstrip("\ufeff"), newline="")
    reader = csv.reader(stream, strict=True)
    try:
        first = next(reader)
        first = [part.strip().lstrip("\ufeff") for part in first]
        has_header = tuple(first[:3]) == _HEADER_PREFIX
        if has_header and (
            len(first) != _EXPECTED_WIDTH[kind]
            or len(set(first)) != len(first)
        ):
            raise UnsafeNarSource("NAR_HEADER_SCHEMA_DRIFT")
        # Headerless positional data is supported only at the exact official
        # width, never by guessing or fuzzy column mappings.
        records = [] if has_header else [first]
        records.extend(reader)
    except (csv.Error, StopIteration):
        raise UnsafeNarSource("NAR_CSV_MALFORMED") from None
    if not records or len(records) > _MAX_ROWS:
        raise UnsafeNarSource("NAR_CSV_ROW_COUNT_INVALID")
    parsed: list[tuple[RaceKey, list[str]]] = []
    for row in records:
        if len(row) != _EXPECTED_WIDTH[kind]:
            raise UnsafeNarSource("NAR_CSV_SCHEMA_DRIFT")
        parsed.append((_race_key(row, month), row))
    return parsed


def _payout_pairs(row: list[str], pairs: tuple[tuple[int, int], ...]
                  ) -> dict[int, int]:
    out: dict[int, int] = {}
    for num_idx, pay_idx in pairs:
        number = _optional_number(
            row[num_idx], "NAR_PAYOUT_NUMBER_INVALID", maximum=18
        )
        amount = _optional_number(
            row[pay_idx], "NAR_PAYOUT_AMOUNT_INVALID"
        )
        if number is None and amount is None:
            continue
        if number is None or number < 1 or amount is None or amount < 100:
            raise UnsafeNarSource("NAR_PAYOUT_PAIR_INCOMPLETE")
        if number in out:
            raise UnsafeNarSource("NAR_DUPLICATE_PAYOUT_HORSE")
        out[number] = amount
    return out


def normalize_nar_published_results(
    csv_texts: Mapping[str, str], *, month: str
) -> NarInMemoryResult:
    """Validate official-width post-result data *in memory only*.

    Caller provides decoded text (UTF-8/CP932 chosen by a separately
    authorized local stage). Do not call with user archive data until
    source-specific rights and the execution path are approved. The
    normalization itself cannot prove pre-race feature availability.
    """
    if (not isinstance(csv_texts, Mapping)
            or set(csv_texts) != set(_EXPECTED_WIDTH)
            or not isinstance(month, str) or len(month) != 6
            or not month.isascii() or not month.isdecimal()):
        raise UnsafeNarSource("NAR_EXPLICIT_THREE_CSVS_AND_MONTH_REQUIRED")
    try:
        parsed = {kind: _parse(csv_texts[kind], kind, month)
                  for kind in _EXPECTED_WIDTH}
    except (KeyError, TypeError):
        raise UnsafeNarSource("NAR_CSV_INPUT_INVALID") from None

    races: dict[RaceKey, list[str]] = {}
    for key, row in parsed["racelist"]:
        if key in races:
            raise UnsafeNarSource("NAR_DUPLICATE_RACE_LIST_ROW")
        # No mixed ban'ei or nonflat running in this particular study.
        if "帯広" in key[0] or row[21].strip() not in ("芝", "ダート"):
            raise UnsafeNarSource("NAR_NONSTANDARD_RACE_TYPE")
        races[key] = row

    entrants: dict[RaceKey, dict[int, int]] = {}
    for key, row in parsed["horselist"]:
        num = _numeric(row[5], "NAR_STARTER_NUMBER_INVALID",
                       minimum=1, maximum=18)
        rank = _numeric(row[31], "NAR_FINISH_RANK_INVALID",
                        minimum=1, maximum=18)
        bag = entrants.setdefault(key, {})
        if num in bag:
            raise UnsafeNarSource("NAR_DUPLICATE_STARTER")
        if not row[6].strip():
            raise UnsafeNarSource("NAR_STARTER_NAME_MISSING")
        bag[num] = rank

    payouts: dict[RaceKey, list[str]] = {}
    for key, row in parsed["payback"]:
        if key in payouts:
            # In NAR, an extra row can signify a dead heat. A standard
            # two-ticket protocol must reject rather than pick one.
            raise UnsafeNarSource("NAR_DEAD_HEAT_OR_DUPLICATE_PAYOUT")
        payouts[key] = row

    if not races or set(races) != set(entrants) or set(races) != set(payouts):
        raise UnsafeNarSource("NAR_RACE_COVERAGE_MISMATCH")

    resolved: list[NarCompleteRace] = []
    nstarters = 0
    years: list[int] = []
    for key in sorted(races):
        entrants_by_num = entrants[key]
        n = len(entrants_by_num)
        if not 5 <= n <= 18:
            raise UnsafeNarSource("NAR_UNSUPPORTED_FIELD_SIZE")
        if set(entrants_by_num.values()) != set(range(1, n + 1)):
            raise UnsafeNarSource("NAR_DEAD_HEAT_SCRATCH_OR_INCOMPLETE_RANKS")
        declared = _numeric(races[key][26], "NAR_DECLARED_STARTERS_INVALID",
                            minimum=5, maximum=18)
        if declared != n:
            raise UnsafeNarSource("NAR_RACE_STARTER_COUNT_MISMATCH")
        row = payouts[key]
        wins = _payout_pairs(row, ((4, 5),))
        places = _payout_pairs(row, ((7, 8), (10, 11), (13, 14)))
        winner = {number for number, rank in entrants_by_num.items()
                  if rank == 1}
        place_cutoff = 2 if n <= 7 else 3
        placers = {number for number, rank in entrants_by_num.items()
                   if rank <= place_cutoff}
        if set(wins) != winner or set(places) != placers:
            raise UnsafeNarSource("NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS")
        resolved.append(NarCompleteRace(
            race_key=key,
            finish_by_number=tuple(sorted(entrants_by_num.items())),
            win_return_by_number=tuple(
                (number, wins.get(number, 0)) for number in sorted(entrants_by_num)
            ),
            place_return_by_number=tuple(
                (number, places.get(number, 0)) for number in sorted(entrants_by_num)
            ),
        ))
        years.append(int(key[1][:4]))
        nstarters += n

    return NarInMemoryResult(
        audit=NarHistoricalAudit(
            status="NAR_PUBLISHED_RESULTS_ONLY_PRE_EVENT_AND_RIGHTS_UNVERIFIED",
            checked_races=len(resolved), checked_starters=nstarters,
            min_year=min(years), max_year=max(years),
        ),
        races=tuple(resolved),
    )
