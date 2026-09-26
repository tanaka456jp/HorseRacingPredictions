from datetime import datetime, timezone

import pandas as pd
import pytest

from horse_racing_predictions.data_sources import normalize_future_entries
from horse_racing_predictions.odds_provider import CsvOddsSnapshotProvider
from horse_racing_predictions.paper_input import prepare_paper_input


def test_future_entry_normalization_accepts_japanese_headers():
    raw = pd.DataFrame({
        "レースID": ["F1"],
        "レース日付": ["2026-10-20"],
        "馬名": ["ALPHA"],
        "馬番": [3],
        "距離(m)": [1600],
        "競馬場名": ["京都"],
    })
    out = normalize_future_entries(raw)
    assert out.loc[0, "race_id"] == "F1"
    assert out.loc[0, "horse_name"] == "ALPHA"
    assert out.loc[0, "post_position"] == 3
    assert out.loc[0, "distance_m"] == 1600


def test_prepare_paper_input_uses_latest_snapshot_before_decision(tmp_path):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time,source_reference\n"
        "F1,F1-3,ALPHA,6.0,2026-10-20T05:00:00+00:00,"
        "2026-10-20T05:30:00+00:00,q1\n"
        "F1,F1-3,ALPHA,5.5,2026-10-20T05:10:00+00:00,"
        "2026-10-20T05:30:00+00:00,q2\n"
        "F1,F1-3,ALPHA,4.0,2026-10-20T05:25:00+00:00,"
        "2026-10-20T05:30:00+00:00,q3\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "F1",
        "horse_id": "F1-3",
        "horse_name": "ALPHA",
        "predicted_win_probability": 0.25,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])
    provider = CsvOddsSnapshotProvider(odds_path)
    decision = datetime(
        2026, 10, 20, 5, 15, tzinfo=timezone.utc
    )

    out = prepare_paper_input(
        prediction,
        provider,
        decision,
    )
    assert out.loc[0, "decimal_odds"] == 5.5
    assert out.loc[0, "source_reference"] == "q2"
    assert out.loc[0, "predicted_at"] == decision.isoformat()


def test_prepare_paper_input_rejects_post_time_decision(tmp_path):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n"
        "F1,F1-3,ALPHA,5.5,2026-10-20T05:10:00+00:00,"
        "2026-10-20T05:30:00+00:00\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "F1",
        "horse_id": "F1-3",
        "horse_name": "ALPHA",
        "predicted_win_probability": 0.25,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])

    with pytest.raises(ValueError, match="no eligible pre-race odds"):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 31, tzinfo=timezone.utc),
        )
