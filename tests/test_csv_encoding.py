import io
import zipfile

import pandas as pd

from horse_racing_predictions.data_sources import (
    load_jra_history_csv,
)


def _history_frame():
    return pd.DataFrame([
        {
            "レースID": "R1",
            "レース日付": "2021-07-31",
            "着順": 1,
            "馬名": "テスト馬A",
            "単勝": 2.5,
        },
        {
            "レースID": "R1",
            "レース日付": "2021-07-31",
            "着順": 2,
            "馬名": "テスト馬B",
            "単勝": 4.0,
        },
    ])


def test_load_history_supports_euc_jp(tmp_path):
    path = tmp_path / "history_euc.csv"
    _history_frame().to_csv(
        path,
        index=False,
        encoding="euc_jp",
    )

    loaded = load_jra_history_csv(path)

    assert list(loaded["horse_name"]) == [
        "テスト馬A",
        "テスト馬B",
    ]
    assert str(loaded["race_date"].max().date()) == "2021-07-31"


def test_load_history_supports_cp932(tmp_path):
    path = tmp_path / "history_cp932.csv"
    _history_frame().to_csv(
        path,
        index=False,
        encoding="cp932",
    )

    loaded = load_jra_history_csv(path)

    assert list(loaded["horse_name"]) == [
        "テスト馬A",
        "テスト馬B",
    ]


def test_load_history_supports_zip_wrapped_csv_named_as_csv(tmp_path):
    path = tmp_path / "19860105-20210731_race_result.csv"

    buffer = io.StringIO()
    _history_frame().to_csv(
        buffer,
        index=False,
    )
    payload = buffer.getvalue().encode("utf-8-sig")

    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "19860105-20210731_race_result.csv",
            payload,
        )

    loaded = load_jra_history_csv(path)

    assert len(loaded) == 2
    assert list(loaded["horse_name"]) == [
        "テスト馬A",
        "テスト馬B",
    ]
