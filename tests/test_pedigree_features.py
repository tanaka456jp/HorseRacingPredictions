import pandas as pd

from horse_racing_predictions.pedigree_features import (
    attach_pedigree_history_features,
)


def _pedigree():
    return pd.DataFrame([
        {
            "blood_registration_number": "H1",
            "sire_breeding_registration_number": "S1",
            "damsire_breeding_registration_number": "D1",
        },
        {
            "blood_registration_number": "H2",
            "sire_breeding_registration_number": "S1",
            "damsire_breeding_registration_number": "D1",
        },
        {
            "blood_registration_number": "H3",
            "sire_breeding_registration_number": "S1",
            "damsire_breeding_registration_number": "D1",
        },
    ])


def test_pedigree_features_use_prior_days_only_and_never_raw_ids():
    frame = pd.DataFrame([
        {
            "race_id": "2024-01-01:R1",
            "race_date": "2024-01-01 10:00:00",
            "finish_position": 1,
            "_jv_blood_registration_number": "H1",
        },
        {
            "race_id": "2024-01-01:R2",
            "race_date": "2024-01-01 15:00:00",
            "finish_position": 6,
            "_jv_blood_registration_number": "H2",
        },
        {
            "race_id": "2024-01-02:R1",
            "race_date": "2024-01-02 10:00:00",
            "finish_position": 2,
            "_jv_blood_registration_number": "H3",
        },
    ])

    result = attach_pedigree_history_features(frame, _pedigree())
    out = result.frame

    # Same-day races must not see one another's outcomes.
    assert out.loc[0, "sire_past_starts"] == 0
    assert out.loc[1, "sire_past_starts"] == 0
    assert out.loc[0, "damsire_past_starts"] == 0
    assert out.loc[1, "damsire_past_starts"] == 0

    # The next calendar day sees both prior-day starts.
    assert out.loc[2, "sire_past_starts"] == 2
    assert out.loc[2, "sire_past_win_rate"] == 0.5
    assert out.loc[2, "sire_past_top3_rate"] == 0.5
    assert out.loc[2, "sire_days_since_seen"] == 1
    assert out.loc[2, "damsire_past_starts"] == 2

    assert result.matched_rows == 3
    assert result.total_rows == 3
    assert all("registration_number" not in c for c in result.feature_columns)
    assert "sire_breeding_registration_number" not in out.columns
    assert "damsire_breeding_registration_number" not in out.columns


def test_unmatched_horse_is_allowed_but_generates_no_fake_lineage_history():
    frame = pd.DataFrame([
        {
            "race_id": "2024-01-03:R1",
            "race_date": "2024-01-03",
            "finish_position": 4,
            "_jv_blood_registration_number": "UNKNOWN",
        }
    ])

    result = attach_pedigree_history_features(frame, _pedigree())
    assert result.matched_rows == 0
    assert result.total_rows == 1
    assert result.feature_columns == ()


def test_existing_field_size_is_preserved():
    frame = pd.DataFrame([
        {
            "race_id": "R1",
            "race_date": "2024-01-01",
            "finish_position": 1,
            "field_size": 18.0,
            "_jv_blood_registration_number": "H1",
        },
        {
            "race_id": "R2",
            "race_date": "2024-01-02",
            "finish_position": 3,
            "field_size": 18.0,
            "_jv_blood_registration_number": "H2",
        },
    ])

    result = attach_pedigree_history_features(frame, _pedigree())
    assert result.frame["field_size"].tolist() == [18.0, 18.0]
    assert result.frame.loc[1, "sire_past_avg_finish_percentile"] == 0.0
