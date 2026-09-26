from datetime import datetime, timezone

import pandas as pd
import pytest

from horse_racing_predictions.jravan import JraVanApiError
from horse_racing_predictions.jravan_trial import (
    acquire_trial_race_raw,
    filter_after_base_history,
    recent_normal_from_time,
    resolve_approved_base_history,
    resume_current_history_from_parsed,
)


def test_filter_after_base_history_removes_overlap():
    base = pd.DataFrame([
        {
            "race_id": "B1",
            "race_date": "2021-07-31",
            "horse_name": "A",
        }
    ])
    parsed = pd.DataFrame([
        {
            "race_id": "OLD",
            "race_date": "2021-07-31",
            "post_position": 1,
            "horse_name": "OLD",
        },
        {
            "race_id": "NEW1",
            "race_date": "2021-08-01",
            "post_position": 2,
            "horse_name": "B",
        },
        {
            "race_id": "NEW2",
            "race_date": "2026-09-26",
            "post_position": 1,
            "horse_name": "C",
        },
    ])

    supplement, base_end = filter_after_base_history(
        base,
        parsed,
    )

    assert str(base_end.date()) == "2021-07-31"
    assert list(supplement["race_id"]) == [
        "NEW1",
        "NEW2",
    ]


def test_filter_after_base_history_rejects_empty_frames():
    with pytest.raises(ValueError, match="base history is empty"):
        filter_after_base_history(
            pd.DataFrame(),
            pd.DataFrame([{
                "race_date": "2021-08-01",
            }]),
        )

    with pytest.raises(ValueError, match="parsed JRA-VAN history is empty"):
        filter_after_base_history(
            pd.DataFrame([{
                "race_date": "2021-07-31",
            }]),
            pd.DataFrame(),
        )


def test_resolve_approved_base_history_uses_explicit_path(tmp_path):
    path = tmp_path / "base.csv"
    path.write_text("x\n", encoding="utf-8")
    assert resolve_approved_base_history(path) == path


def test_resolve_approved_base_history_uses_kagglehub_when_missing(
    tmp_path,
    monkeypatch,
):
    dataset_dir = tmp_path / "download"
    dataset_dir.mkdir()
    expected = dataset_dir / "19860105-20210731_race_result.csv"
    expected.write_text("x\n", encoding="utf-8")

    class FakeKaggleHub:
        @staticmethod
        def dataset_download(handle, path, output_dir):
            assert handle == "takamotoki/jra-horse-racing-dataset"
            assert path == "19860105-20210731_race_result.csv"
            return str(dataset_dir)

    monkeypatch.setitem(
        __import__("sys").modules,
        "kagglehub",
        FakeKaggleHub,
    )

    resolved = resolve_approved_base_history(
        None,
        cache_dir=tmp_path / "cache",
    )
    assert resolved == expected


def test_recent_normal_from_time_uses_recent_year():
    value = recent_normal_from_time(
        now=datetime(
            2026, 9, 26, 12, 0,
            tzinfo=timezone.utc,
        )
    )
    assert value == "20250926000000"


def test_trial_acquisition_falls_back_to_option1_on_301(tmp_path):
    calls = []

    def exporter(**kwargs):
        calls.append({
            "from_time": kwargs["from_time"],
            "option": kwargs["option"],
        })
        if len(calls) == 1:
            raise JraVanApiError(
                "JVOpen failed with return code -301"
            )
        return object()

    (
        _summary,
        mode,
        effective_from,
        effective_option,
        reason,
    ) = acquire_trial_race_raw(
        output_path=tmp_path / "raw.jsonl",
        summary_path=tmp_path / "summary.json",
        setup_from_time="20210801000000",
        setup_option=4,
        recent_days=365,
        now=datetime(
            2026, 9, 26, 12, 0,
            tzinfo=timezone.utc,
        ),
        exporter=exporter,
    )

    assert calls == [
        {
            "from_time": "20210801000000",
            "option": 4,
        },
        {
            "from_time": "20250926000000",
            "option": 1,
        },
    ]
    assert mode == "recent_normal_fallback"
    assert effective_from == "20250926000000"
    assert effective_option == 1
    assert "-301" in reason


def test_trial_acquisition_does_not_hide_non_auth_errors(tmp_path):
    def exporter(**kwargs):
        raise JraVanApiError(
            "JVOpen failed with return code -305"
        )

    with pytest.raises(
        JraVanApiError,
        match="return code -305",
    ):
        acquire_trial_race_raw(
            output_path=tmp_path / "raw.jsonl",
            summary_path=tmp_path / "summary.json",
            setup_from_time="20210801000000",
            exporter=exporter,
        )


def test_resume_current_history_reuses_existing_parsed_file(tmp_path):
    base_path = tmp_path / "base.csv"
    pd.DataFrame([
        {
            "race_id": "B1",
            "race_date": "2021-07-31",
            "finish_position": 1,
            "horse_name": "BASE_A",
            "win_odds": 2.0,
        },
        {
            "race_id": "B1",
            "race_date": "2021-07-31",
            "finish_position": 2,
            "horse_name": "BASE_B",
            "win_odds": 4.0,
        },
    ]).to_csv(
        base_path,
        index=False,
        encoding="utf-8-sig",
    )

    output_dir = tmp_path / "full"
    output_dir.mkdir()
    parsed_path = output_dir / "parsed_history.csv"
    pd.DataFrame([
        {
            "race_id": "N1",
            "race_date": "2026-09-20",
            "finish_position": 1,
            "post_position": 1,
            "horse_name": "NEW_A",
            "win_odds": 3.0,
        },
        {
            "race_id": "N1",
            "race_date": "2026-09-20",
            "finish_position": 2,
            "post_position": 2,
            "horse_name": "NEW_B",
            "win_odds": 5.0,
        },
    ]).to_csv(
        parsed_path,
        index=False,
        encoding="utf-8-sig",
    )

    artifact_dir = tmp_path / "artifacts"
    summary = resume_current_history_from_parsed(
        base_path=base_path,
        output_dir=output_dir,
        artifact_dir=artifact_dir,
    )

    assert summary.acquisition_mode == "resume_existing_parsed"
    assert summary.supplemental_rows_after_base == 2
    assert summary.current_history_end == "2026-09-20"
    assert (output_dir / "current_history.csv").exists()
    assert (artifact_dir / "pipeline_summary.json").exists()
