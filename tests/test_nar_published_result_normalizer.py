"""Official-position NAR normalized settlement tests; FICTIONAL rows only.

No NAR ZIP downloaded or decompressed. No real horse, dates or returns.
"""
from __future__ import annotations

import csv
from io import StringIO

import pytest

from horse_racing_predictions.nar_published_result_normalizer import (
    normalize_nar_published_results,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource


def _encode(rows):
    buf = StringIO(newline="")
    out = csv.writer(buf)
    out.writerows(rows)
    return buf.getvalue()


def _fixture(*, starters=8, duplicate_payback=False,
             with_header=False, month="202402"):
    race = [""] * 68
    race[0], race[1], race[2] = "架空競馬場", f"{month}14", "3"
    race[21], race[26] = "ダート", str(starters)
    entries = []
    for rank in range(1, starters + 1):
        row = [""] * 36
        row[0:3] = race[0:3]
        row[5], row[6], row[31] = str(rank), f"架空馬{rank}", str(rank)
        row[35] = str(starters - rank + 1)  # popularity MUST be ignored
        entries.append(row)
    pay = [""] * 54
    pay[0:3] = race[0:3]
    pay[4], pay[5] = "1", "250"
    places = 2 if starters <= 7 else 3
    for position, (num_field, payout_field) in enumerate(
        ((7, 8), (10, 11), (13, 14)), 1
    ):
        if position <= places:
            pay[num_field] = str(position)
            pay[payout_field] = str(100 + position * 10)
    mapped = {
        "racelist": [race],
        "horselist": entries,
        "payback": [pay, pay.copy()] if duplicate_payback else [pay],
    }
    if with_header:
        for kind, records in mapped.items():
            columns = [f"列{i}" for i in range(len(records[0]))]
            columns[:3] = ["競馬場", "競走年月日", "レース番号"]
            mapped[kind] = [columns, *records]
    return {kind: _encode(records) for kind, records in mapped.items()}


@pytest.mark.parametrize("starters", [5, 7, 8, 18])
@pytest.mark.parametrize("with_header", [False, True])
def test_complete_fictional_race_normalization(starters, with_header):
    sample = _fixture(starters=starters, with_header=with_header)
    report = normalize_nar_published_results(sample, month="202402")
    assert report.audit.checked_races == 1
    assert report.audit.checked_starters == starters
    assert report.audit.min_year == report.audit.max_year == 2024
    assert not report.audit.pre_event_snapshot_verified
    assert not report.audit.authorized_for_model_training
    assert not report.audit.positive_ev_demonstrated
    assert not report.audit.publication_authorized
    assert len(report.races) == 1
    race = report.races[0]
    assert dict(race.finish_by_number)[1] == 1
    assert dict(race.win_return_by_number)[1] == 250
    assert dict(race.win_return_by_number)[2] == 0
    assert dict(race.place_return_by_number)[1] == 110
    assert dict(race.place_return_by_number)[2] == 120
    if starters >= 8:
        assert dict(race.place_return_by_number)[3] == 130
    else:
        assert dict(race.place_return_by_number)[3] == 0
    assert "架空馬" not in repr(report)
    assert "架空競馬場" not in repr(report)


def test_payback_is_one_row_per_race_not_per_horse():
    sample = _fixture(starters=8)
    # A single payback row is shared across eight runner results.
    report = normalize_nar_published_results(sample, month="202402")
    assert report.audit.checked_starters == 8
    assert report.audit.checked_races == 1


def test_tie_or_duplicate_payback_row_rejected():
    sample = _fixture(duplicate_payback=True)
    with pytest.raises(UnsafeNarSource, match="NAR_IDENTICAL_DUPLICATE_PAYOUT_ROW"):
        normalize_nar_published_results(sample, month="202402")


def test_wrong_payout_number_cannot_create_fake_profit():
    sample = _fixture()
    source = list(csv.reader(StringIO(sample["payback"])))
    source[0][4] = "2"
    sample["payback"] = _encode(source)
    with pytest.raises(UnsafeNarSource, match="NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS"):
        normalize_nar_published_results(sample, month="202402")


def test_payout_below_face_stake_is_rejected():
    sample = _fixture()
    source = list(csv.reader(StringIO(sample["payback"])))
    source[0][5] = "90"
    sample["payback"] = _encode(source)
    with pytest.raises(UnsafeNarSource, match="NAR_PAYOUT_PAIR_INCOMPLETE"):
        normalize_nar_published_results(sample, month="202402")


def test_outcome_rank_tie_must_not_be_overcounted():
    sample = _fixture()
    source = list(csv.reader(StringIO(sample["horselist"])))
    source[1][31] = "1"
    sample["horselist"] = _encode(source)
    with pytest.raises(UnsafeNarSource, match="NAR_DEAD_HEAT_PAYOUT_SETTLEMENT_UNRESOLVED"):
        normalize_nar_published_results(sample, month="202402")


def test_popularity_mutation_has_no_effect_on_result_normalization():
    sample = _fixture()
    changed = sample.copy()
    source = list(csv.reader(StringIO(changed["horselist"])))
    for i, row in enumerate(source):
        row[35] = str(100 + i)
    changed["horselist"] = _encode(source)
    baseline = normalize_nar_published_results(sample, month="202402")
    altered = normalize_nar_published_results(changed, month="202402")
    assert baseline.races == altered.races


def test_post2024_protected_period_is_refused():
    sample = _fixture(month="202502")
    with pytest.raises(UnsafeNarSource, match="NAR_PROTECTED_OR_INVALID_DATE"):
        normalize_nar_published_results(sample, month="202502")


def test_wrong_month_not_silently_mixed():
    sample = _fixture(month="202403")
    with pytest.raises(UnsafeNarSource, match="NAR_DATE_OUTSIDE_ARCHIVE_MONTH"):
        normalize_nar_published_results(sample, month="202402")


def test_racelist_must_agree_on_starter_count():
    sample = _fixture()
    source = list(csv.reader(StringIO(sample["racelist"])))
    source[0][26] = "9"
    sample["racelist"] = _encode(source)
    with pytest.raises(UnsafeNarSource, match="NAR_RACE_STARTER_COUNT_MISMATCH"):
        normalize_nar_published_results(sample, month="202402")


def test_no_markets_in_post_result_summaries():
    sample = _fixture()
    report = normalize_nar_published_results(sample, month="202402")
    assert "popularity" not in repr(report).lower()
    assert "odds" not in repr(report).lower()
    assert not report.audit.pre_event_snapshot_verified


def test_missing_any_member_is_refused():
    sample = _fixture()
    sample.pop("payback")
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLICIT_THREE_CSVS_AND_MONTH_REQUIRED"):
        normalize_nar_published_results(sample, month="202402")


def test_malformed_column_width_is_refused():
    sample = _fixture()
    sample["racelist"] = "架空競馬場,20240214,3\n"
    with pytest.raises(UnsafeNarSource, match="NAR_CSV_SCHEMA_DRIFT"):
        normalize_nar_published_results(sample, month="202402")


def test_banei_not_mixed_with_flat_nar_sample():
    sample = _fixture()
    src = list(csv.reader(StringIO(sample["racelist"])))
    src[0][0] = "帯広"
    sample["racelist"] = _encode(src)
    with pytest.raises(UnsafeNarSource, match="NAR_NONSTANDARD_RACE_TYPE"):
        normalize_nar_published_results(sample, month="202402")


def test_csv_text_limit_refused():
    sample = _fixture()
    sample["racelist"] = "A" * 16_000_001
    with pytest.raises(UnsafeNarSource, match="NAR_CSV_TEXT_INVALID"):
        normalize_nar_published_results(sample, month="202402")


def _legacy_2017_racelist(sample: dict[str, str]) -> dict[str, str]:
    """Synthetic old 66-field headered racelist; all other members unchanged."""
    changed = dict(sample)
    rows = list(csv.reader(StringIO(sample["racelist"])))
    changed["racelist"] = _encode([row[:66] for row in rows])
    return changed


def test_2017_headered_66_column_racelist_keeps_original_used_positions():
    sample = _legacy_2017_racelist(
        _fixture(month="201711", with_header=True)
    )
    from horse_racing_predictions.nar_published_result_normalizer import _parse
    parsed = _parse(sample["racelist"], "racelist", "201711")
    assert len(parsed) == 1
    raw = parsed[0][1]
    assert len(raw) == 68  # padding at the END; no field shifts
    assert raw[21] == "ダート"
    assert raw[26] == "8"
    assert raw[66:] == ["", ""]
    normalized = normalize_nar_published_results(sample, month="201711")
    assert normalized.audit.checked_races == 1
    assert normalized.audit.checked_starters == 8
    assert not normalized.audit.pre_event_snapshot_verified
    assert not normalized.audit.positive_ev_demonstrated


def test_legacy_66_width_requires_actual_header_not_implicit_guess():
    sample = _legacy_2017_racelist(
        _fixture(month="201711", with_header=False)
    )
    with pytest.raises(UnsafeNarSource, match="NAR_CSV_SCHEMA_DRIFT"):
        normalize_nar_published_results(sample, month="201711")


def test_legacy_66_not_accepted_for_2024_or_as_arbitrary_short_data():
    sample = _legacy_2017_racelist(
        _fixture(month="202402", with_header=True)
    )
    with pytest.raises(UnsafeNarSource, match="NAR_HEADER_SCHEMA_DRIFT"):
        normalize_nar_published_results(sample, month="202402")

    sample = _fixture(month="201711", with_header=True)
    rows = list(csv.reader(StringIO(sample["racelist"])))
    rows[0] = rows[0][:66]
    sample["racelist"] = _encode(rows)
    with pytest.raises(UnsafeNarSource, match="NAR_CSV_SCHEMA_DRIFT"):
        normalize_nar_published_results(sample, month="201711")


def test_legacy_66_wrong_field_cannot_hide_malformed_training_race():
    sample = _legacy_2017_racelist(
        _fixture(month="201711", with_header=True)
    )
    rows = list(csv.reader(StringIO(sample["racelist"])))
    rows[1][26] = "12"  # mismatch against eight actual starters
    sample["racelist"] = _encode(rows)
    with pytest.raises(UnsafeNarSource, match="NAR_RACE_STARTER_COUNT_MISMATCH"):
        normalize_nar_published_results(sample, month="201711")


@pytest.mark.parametrize(("raw_finish", "error"), [
    ("", "NAR_OFFICIAL_BLANK_FINISH_STATUS_UNRESOLVED"),
    ("取消", "NAR_OFFICIAL_EXCEPTION_SETTLEMENT_UNRESOLVED"),
    ("除外", "NAR_OFFICIAL_EXCEPTION_SETTLEMENT_UNRESOLVED"),
    ("中止", "NAR_OFFICIAL_EXCEPTION_SETTLEMENT_UNRESOLVED"),
    ("失格", "NAR_OFFICIAL_EXCEPTION_SETTLEMENT_UNRESOLVED"),
    ("取止", "NAR_OFFICIAL_EXCEPTION_SETTLEMENT_UNRESOLVED"),
    ("不成", "NAR_OFFICIAL_EXCEPTION_SETTLEMENT_UNRESOLVED"),
    ("3降", "NAR_DEMOTED_FINISH_SETTLEMENT_UNRESOLVED"),
    ("?", "NAR_FINISH_RANK_INVALID"),
])
def test_official_non_numeric_finish_is_preserved_as_unsettled_not_as_a_loss(raw_finish, error):
    sample = _fixture()
    rows = list(csv.reader(StringIO(sample["horselist"])))
    rows[1][31] = raw_finish
    sample["horselist"] = _encode(rows)
    with pytest.raises(UnsafeNarSource, match=error):
        normalize_nar_published_results(sample, month="202402")


def test_distinct_multiple_payback_rows_require_actual_dead_heat_settlement_review():
    sample = _fixture()
    rows = list(csv.reader(StringIO(sample["payback"])))
    alternate = rows[0].copy()
    alternate[4] = "2"
    sample["payback"] = _encode([rows[0], alternate])
    with pytest.raises(UnsafeNarSource, match="NAR_OFFICIAL_MULTIROW_PAYOUT_SETTLEMENT_UNRESOLVED"):
        normalize_nar_published_results(sample, month="202402")


@pytest.mark.parametrize(("ranks", "expected"), [
    ([1, 2, 3, 4], "COMPLETE"),
    ([1, 1, 3, 4], "DEAD_HEAT"),
    ([1, 2, 2, 4], "DEAD_HEAT"),
    ([1, 1, 2, 4], "INCOMPLETE"),
    ([1, 2, 4], "INCOMPLETE"),
])
def test_competition_rank_sequence_never_relabels_ties(ranks, expected):
    from horse_racing_predictions.nar_published_result_normalizer import _competition_rank_sequence
    assert _competition_rank_sequence(ranks) == expected
