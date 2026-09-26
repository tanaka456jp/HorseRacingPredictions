import pandas as pd
import pytest

from horse_racing_predictions.jravan_trial import (
    filter_after_base_history,
    resolve_approved_base_history,
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
