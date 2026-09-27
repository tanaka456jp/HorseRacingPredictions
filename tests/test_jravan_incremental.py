import pandas as pd
import pytest

from horse_racing_predictions.jravan_incremental import (
    incremental_from_time,
    merge_completed_increment,
)


def _frame(rows):
    return pd.DataFrame(rows)


def test_incremental_from_time_uses_overlap_window():
    existing = _frame([
        {
            "race_id": "R1",
            "race_date": "2026-09-22",
            "post_position": 1,
            "finish_position": 1,
        }
    ])

    assert (
        incremental_from_time(existing, overlap_days=7)
        == "20260915000000"
    )


def test_merge_completed_increment_replaces_whole_race_and_adds_new():
    existing = _frame([
        {
            "race_id": "R1",
            "race_date": "2026-09-20",
            "post_position": 1,
            "finish_position": 1,
            "win_odds": 2.0,
        },
        {
            "race_id": "R1",
            "race_date": "2026-09-20",
            "post_position": 2,
            "finish_position": 2,
            "win_odds": 3.0,
        },
        {
            "race_id": "R0",
            "race_date": "2026-09-19",
            "post_position": 1,
            "finish_position": 1,
            "win_odds": 4.0,
        },
    ])
    update = _frame([
        {
            "race_id": "R1",
            "race_date": "2026-09-20",
            "post_position": 1,
            "finish_position": 2,
            "win_odds": 2.1,
        },
        {
            "race_id": "R1",
            "race_date": "2026-09-20",
            "post_position": 2,
            "finish_position": 1,
            "win_odds": 3.2,
        },
        {
            "race_id": "R2",
            "race_date": "2026-09-21",
            "post_position": 1,
            "finish_position": 1,
            "win_odds": 5.0,
        },
        {
            "race_id": "R2",
            "race_date": "2026-09-21",
            "post_position": 2,
            "finish_position": 2,
            "win_odds": 6.0,
        },
    ])

    merged, replaced = merge_completed_increment(existing, update)

    assert replaced == 2
    assert len(merged) == 5
    r1 = merged.loc[merged["race_id"] == "R1"]
    assert len(r1) == 2
    assert int(
        r1.loc[r1["post_position"] == 2, "finish_position"].iloc[0]
    ) == 1
    assert set(merged["race_id"]) == {"R0", "R1", "R2"}


def test_merge_empty_update_preserves_existing():
    existing = _frame([
        {
            "race_id": "R1",
            "race_date": "2026-09-20",
            "post_position": 1,
            "finish_position": 1,
        }
    ])
    merged, replaced = merge_completed_increment(
        existing,
        pd.DataFrame(),
    )

    assert replaced == 0
    pd.testing.assert_frame_equal(merged, existing)


def test_incremental_from_time_rejects_empty_history():
    with pytest.raises(ValueError, match="empty"):
        incremental_from_time(pd.DataFrame(), overlap_days=7)
