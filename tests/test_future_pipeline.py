from datetime import datetime, timezone
from pathlib import Path

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


def test_prepare_paper_input_rejects_duplicate_rows(tmp_path):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n"
        "F1,F1-3,ALPHA,5.5,2026-10-20T05:10:00+00:00,"
        "2026-10-20T05:30:00+00:00\n"
        "F2,F2-1,BETA,4.0,2026-10-20T05:10:00+00:00,"
        "2026-10-20T05:30:00+00:00\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([
        {
            "race_id": "F1",
            "horse_id": "F1-3",
            "horse_name": "ALPHA",
            "predicted_win_probability": 0.25,
            "confidence": 0.7,
            "model_version": "champion-v7",
        },
        {
            "race_id": "F1",
            "horse_id": "F1-3",
            "horse_name": "ALPHA",
            "predicted_win_probability": 0.3,
            "confidence": 0.8,
            "model_version": "champion-v7",
        },
        {
            "race_id": "F2",
            "horse_id": "F2-1",
            "horse_name": "BETA",
            "predicted_win_probability": 0.2,
            "confidence": 0.6,
            "model_version": "champion-v7",
        },
    ])

    with pytest.raises(ValueError, match="duplicate.*race_id.*horse_id"):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
        )


def test_prepare_paper_input_rejects_blank_race_id_before_odds_resolution(tmp_path):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "   ",
        "horse_id": "F1-3",
        "horse_name": "ALPHA",
        "predicted_win_probability": 0.25,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])

    with pytest.raises(ValueError, match="race_id.*blank or whitespace"):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
        )


def test_prepare_paper_input_rejects_blank_horse_name_before_odds_resolution(tmp_path):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "F1",
        "horse_id": "F1-3",
        "horse_name": "   ",
        "predicted_win_probability": 0.25,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])

    with pytest.raises(ValueError, match="horse_name.*blank or whitespace"):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
        )


def test_prepare_paper_input_rejects_blank_horse_id_before_odds_resolution(tmp_path):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "F1",
        "horse_id": "   ",
        "horse_name": "ALPHA",
        "predicted_win_probability": 0.25,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])

    with pytest.raises(ValueError, match="horse_id.*blank or whitespace"):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
        )


def test_forward_paper_summary_includes_sanitized_aggregate_counts():
    source = Path(
        "src/horse_racing_predictions/forward_pipeline.py"
    ).read_text(encoding="utf-8")

    assert '"prediction_rows": int(len(predictions))' in source
    assert 'prediction_races = int(predictions["race_id"].nunique())' in source
    assert '"prediction_races": prediction_races' in source
    assert '"paper_input_rows": int(len(paper_input))' in source
    assert 'paper_input_races = int(paper_input["race_id"].nunique())' in source
    assert '"paper_input_races": paper_input_races' in source
    assert (
        '"paper_input_race_coverage_rate": '
        "paper_input_race_coverage_rate"
    ) in source
    assert "paper_input_races / prediction_races" in source
    assert "if prediction_races > 0" in source
    assert "else None" in source


def test_prepare_paper_input_has_single_blank_race_id_guard():
    source = Path(
        "src/horse_racing_predictions/paper_input.py"
    ).read_text(encoding="utf-8")

    assert source.count(
        "race_id must not be blank or whitespace in predictions"
    ) == 1


@pytest.mark.parametrize(
    "invalid_probability",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
)
def test_prepare_paper_input_rejects_invalid_probability_before_odds_resolution(
    tmp_path,
    invalid_probability,
):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "F1",
        "horse_id": "F1-3",
        "horse_name": "ALPHA",
        "predicted_win_probability": invalid_probability,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])

    with pytest.raises(
        ValueError,
        match="predicted_win_probability.*finite.*\\[0, 1\\]",
    ):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("probability", [0.0, 1.0])
def test_prepare_paper_input_accepts_probability_endpoints(
    tmp_path,
    probability,
):
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
        "predicted_win_probability": probability,
        "confidence": 0.7,
        "model_version": "champion-v7",
    }])

    out = prepare_paper_input(
        prediction,
        CsvOddsSnapshotProvider(odds_path),
        datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
    )

    assert out.loc[0, "predicted_win_probability"] == probability


@pytest.mark.parametrize(
    "invalid_confidence",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
)
def test_prepare_paper_input_rejects_invalid_confidence_before_odds_resolution(
    tmp_path,
    invalid_confidence,
):
    odds_path = tmp_path / "odds.csv"
    odds_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n",
        encoding="utf-8",
    )
    prediction = pd.DataFrame([{
        "race_id": "F1",
        "horse_id": "F1-3",
        "horse_name": "ALPHA",
        "predicted_win_probability": 0.25,
        "confidence": invalid_confidence,
        "model_version": "champion-v7",
    }])

    with pytest.raises(
        ValueError,
        match="confidence.*finite.*\\[0, 1\\]",
    ):
        prepare_paper_input(
            prediction,
            CsvOddsSnapshotProvider(odds_path),
            datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_prepare_paper_input_accepts_confidence_endpoints(
    tmp_path,
    confidence,
):
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
        "confidence": confidence,
        "model_version": "champion-v7",
    }])

    out = prepare_paper_input(
        prediction,
        CsvOddsSnapshotProvider(odds_path),
        datetime(2026, 10, 20, 5, 15, tzinfo=timezone.utc),
    )

    assert out.loc[0, "confidence"] == confidence
