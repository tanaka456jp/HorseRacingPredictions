from datetime import datetime, timezone

import pandas as pd

from horse_racing_predictions.current_history import (
    HistorySourceManifest,
    merge_history,
    validate_history_intake,
)


def _base():
    return pd.DataFrame([
        {
            "race_id": "B1",
            "race_date": "2021-07-31",
            "horse_name": "A",
            "finish_position": 1,
            "win_odds": 2.0,
        },
        {
            "race_id": "B1",
            "race_date": "2021-07-31",
            "horse_name": "B",
            "finish_position": 2,
            "win_odds": 4.0,
        },
    ])


def _supplement(start="2021-08-01"):
    return pd.DataFrame([
        {
            "race_id": "S1",
            "race_date": start,
            "horse_name": "C",
            "finish_position": 1,
            "win_odds": 3.0,
        },
        {
            "race_id": "S1",
            "race_date": start,
            "horse_name": "D",
            "finish_position": 2,
            "win_odds": 5.0,
        },
    ])


def _manifest(approved=True):
    return HistorySourceManifest.create(
        source_name="test supplement",
        source_kind="user_supplied",
        source_reference="local-file",
        rights_note="User confirms lawful use for private research.",
        approved_for_modeling=approved,
        acquired_at=datetime(
            2026, 9, 26, 0, 0,
            tzinfo=timezone.utc,
        ),
    )


def test_clean_adjacent_supplement_is_ready():
    report = validate_history_intake(
        _base(),
        _supplement(),
        _manifest(),
    )
    assert report.ready
    assert report.gap_days == 1
    assert report.merged_rows == 4


def test_unapproved_source_is_blocked():
    report = validate_history_intake(
        _base(),
        _supplement(),
        _manifest(approved=False),
    )
    assert not report.ready
    assert any(
        "not approved_for_modeling" in error
        for error in report.errors
    )


def test_long_history_gap_fails_closed_without_override():
    report = validate_history_intake(
        _base(),
        _supplement("2021-09-01"),
        _manifest(),
        max_gap_days=14,
    )
    assert not report.ready
    assert report.gap_days == 32

    allowed = validate_history_intake(
        _base(),
        _supplement("2021-09-01"),
        _manifest(),
        max_gap_days=14,
        allow_gap=True,
    )
    assert allowed.ready
    assert any(
        "history gap is 32 days" in warning
        for warning in allowed.warnings
    )


def test_duplicate_and_overlap_are_blocked():
    supplement = _supplement()
    supplement = pd.concat(
        [supplement, supplement.iloc[[0]]],
        ignore_index=True,
    )
    report = validate_history_intake(
        _base(),
        supplement,
        _manifest(),
    )
    assert not report.ready
    assert report.duplicate_keys == 1

    overlap = _base().copy()
    report = validate_history_intake(
        _base(),
        overlap,
        _manifest(),
    )
    assert not report.ready
    assert report.overlapping_keys == 2


def test_invalid_race_result_quality_is_blocked():
    supplement = _supplement()
    supplement.loc[:, "finish_position"] = [2, 3]
    supplement.loc[1, "win_odds"] = 1.0

    report = validate_history_intake(
        _base(),
        supplement,
        _manifest(),
    )
    assert not report.ready
    assert report.winner_count_conflicts == 1
    assert report.invalid_odds_rows == 1


def test_merge_adds_provenance_columns():
    base = _base()
    supplement = _supplement()
    manifest = _manifest()
    report = validate_history_intake(
        base,
        supplement,
        manifest,
    )
    merged = merge_history(
        base,
        supplement,
        manifest,
        report,
    )

    assert len(merged) == 4
    supplemental = merged[
        merged["race_id"] == "S1"
    ]
    assert (
        supplemental["_source_name"]
        == "test supplement"
    ).all()
    assert (
        supplemental["_source_kind"]
        == "user_supplied"
    ).all()
