"""Synthetic research-split guard regressions; no real history read."""
import pytest

from horse_racing_predictions.exotic_synthetic_oos_protocol import (
    audit_synthetic_oos_protocol,
)


def sample(**updates):
    item = {
        "synthetic_only": True,
        "embargo_days": 7,
        "train": [
            {"race_id": "S1", "race_date": "2022-12-23"},
            {"race_id": "S2", "race_date": "2022-12-20"},
        ],
        "evaluation": [
            {"race_id": "S3", "race_date": "2023-01-01"},
            {"race_id": "S4", "race_date": "2024-11-25"},
        ],
    }
    item.update(updates)
    return item


def test_7_full_day_embargo_with_unordered_entries():
    x = audit_synthetic_oos_protocol(sample())
    assert x["actual_gap_full_days"] == 8
    assert x["no_race_identity_overlap"] is True
    assert x["training_races"] == 2
    assert x["evaluation_races"] == 2
    assert x["real_oos_verified"] is False
    assert x["economic_return_verified"] is False
    assert x["positive_executable_ev_proven"] is False


def test_exactly_seven_calendar_days_is_accepted():
    x = audit_synthetic_oos_protocol(sample(
        train=[{"race_id": "S1", "race_date": "2022-12-24"}],
        evaluation=[{"race_id": "S2", "race_date": "2023-01-01"}],
    ))
    assert x["actual_gap_full_days"] == 7


@pytest.mark.parametrize("change", [
    {"embargo_days": 6},
    {"embargo_days": True},
    {"embargo_days": "7"},
    {"synthetic_only": False},
    {"train": []},
    {"evaluation": []},
    {"unexpected": "future"},
    {"train": [{"race_id": "S1", "race_date": "2023-01-01"}]},
    {"train": [{"race_id": "S1", "race_date": "2025-01-01"}]},
    {"evaluation": [{"race_id": "S3", "race_date": "2026-01-01"}]},
    {"evaluation": [{"race_id": "S3", "race_date": "2023-02-30"}]},
    {"evaluation": [{"race_id": "S3", "race_date": "2023/02/01"}]},
    {"evaluation": [{"race_id": "20230101", "race_date": "2023-02-01"}]},
    {"train": [{"race_id": "S1", "race_date": "2022-12-23"},
               {"race_id": "S1", "race_date": "2022-12-22"}]},
    {"evaluation": [{"race_id": "S2", "race_date": "2023-01-01"}]},
    {"train": [{"race_id": "S1", "race_date": "2022-12-27"}]},
    {"evaluation": [{"race_id": "S3", "race_date": "2023-01-01",
                      "finish_position": 1}]},
])
def test_fail_closed_for_invalid_or_leaky_splits(change):
    with pytest.raises(ValueError):
        audit_synthetic_oos_protocol(sample(**change))
